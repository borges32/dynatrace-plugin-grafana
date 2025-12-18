package plugin

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/grafana/grafana-plugin-sdk-go/backend"
	"github.com/grafana/grafana-plugin-sdk-go/backend/instancemgmt"
	"github.com/grafana/grafana-plugin-sdk-go/backend/log"
	"github.com/grafana/grafana-plugin-sdk-go/data"
)

// Make sure Datasource implements required interfaces. This is important to do
// since otherwise we will only get a not implemented error response from plugin in
// runtime. In this example datasource instance implements backend.QueryDataHandler,
// backend.CheckHealthHandler interfaces. Plugin should not implement all these
// interfaces - only those which are required for a particular task.
var (
	_ backend.QueryDataHandler      = (*Datasource)(nil)
	_ backend.CheckHealthHandler    = (*Datasource)(nil)
	_ instancemgmt.InstanceDisposer = (*Datasource)(nil)
)

// NewDatasource creates a new datasource instance.
func NewDatasource(settings backend.DataSourceInstanceSettings) (instancemgmt.Instance, error) {
	var jsonData map[string]interface{}
	err := json.Unmarshal(settings.JSONData, &jsonData)
	if err != nil {
		return nil, fmt.Errorf("error unmarshaling settings: %w", err)
	}

	apiUrl := ""
	if url, ok := jsonData["apiUrl"].(string); ok {
		apiUrl = url
	}

	tlsSkipVerify := false
	if skip, ok := jsonData["tlsSkipVerify"].(bool); ok {
		tlsSkipVerify = skip
	}

	apiToken := settings.DecryptedSecureJSONData["apiToken"]
	tlsCertificate := settings.DecryptedSecureJSONData["tlsCertificate"]

	return &Datasource{
		settings:       settings,
		apiUrl:         apiUrl,
		apiToken:       apiToken,
		tlsSkipVerify:  tlsSkipVerify,
		tlsCertificate: tlsCertificate,
	}, nil
}

// Datasource is a Dynatrace datasource which can respond to data queries, reports
// its health and has alerting support.
type Datasource struct {
	settings       backend.DataSourceInstanceSettings
	apiUrl         string
	apiToken       string
	tlsSkipVerify  bool
	tlsCertificate string
}

// Dispose here tells plugin SDK that plugin wants to clean up resources when a new instance
// created. As soon as datasource settings change detected by SDK old datasource instance will
// be disposed and a new one will be created using NewDatasource factory function.
func (d *Datasource) Dispose() {
	// Clean up datasource instance resources.
}

// QueryData handles multiple queries and returns multiple responses.
// req contains the queries []DataQuery (where each query contains RefID as a unique identifier).
// The QueryDataResponse contains a map of RefID to the response for each query, and each response
// contains Frames ([]*Frame).
func (d *Datasource) QueryData(ctx context.Context, req *backend.QueryDataRequest) (*backend.QueryDataResponse, error) {
	log.DefaultLogger.Info("QueryData called", "queries", len(req.Queries))

	// create response struct
	response := backend.NewQueryDataResponse()

	// loop over queries and execute them individually.
	for _, q := range req.Queries {
		res := d.query(ctx, req.PluginContext, q)

		// save the response in a hashmap
		// based on with RefID as identifier
		response.Responses[q.RefID] = res
	}

	return response, nil
}

// queryModel represents the query configuration from frontend
type queryModel struct {
	MetricSelector   string  `json:"metricSelector"` // Primary field: metric with filters/transformations
	MetricId         string  `json:"metricId"`       // DEPRECATED: Use MetricSelector instead
	EntitySelector   string  `json:"entitySelector"` // DEPRECATED: Use filters in MetricSelector
	UseDashboardTime bool    `json:"useDashboardTime"`
	CustomFrom       string  `json:"customFrom"`
	CustomTo         string  `json:"customTo"`
	Resolution       string  `json:"resolution"`
	LabelChart       string  `json:"labelChart"` // Field from labels to use for chart legend
	QueryText        string  `json:"queryText"`
	Constant         float64 `json:"constant"`
}

// DynatraceMetricsResponse represents the response from Dynatrace Metrics V2 API
type DynatraceMetricsResponse struct {
	TotalCount  int                     `json:"totalCount"`
	NextPageKey *string                 `json:"nextPageKey"`
	Resolution  string                  `json:"resolution"`
	Result      []DynatraceMetricResult `json:"result"`
}

type DynatraceMetricResult struct {
	MetricId            string                `json:"metricId"`
	DataPointCountRatio float64               `json:"dataPointCountRatio"`
	DimensionCountRatio float64               `json:"dimensionCountRatio"`
	Data                []DynatraceMetricData `json:"data"`
}

type DynatraceMetricData struct {
	Dimensions   []interface{}     `json:"dimensions"`
	DimensionMap map[string]string `json:"dimensionMap"`
	Timestamps   []int64           `json:"timestamps"`
	Values       []float64         `json:"values"`
}

func (d *Datasource) query(ctx context.Context, pCtx backend.PluginContext, query backend.DataQuery) backend.DataResponse {
	var response backend.DataResponse

	// Unmarshal the JSON into our queryModel.
	var qm queryModel
	err := json.Unmarshal(query.JSON, &qm)
	if err != nil {
		return backend.ErrDataResponse(backend.StatusBadRequest, fmt.Sprintf("json unmarshal: %v", err.Error()))
	}

	// Log raw query JSON for debugging
	log.DefaultLogger.Info("Raw query JSON", "json", string(query.JSON))

	// Determine which field to use (metricSelector takes precedence)
	metricSelector := qm.MetricSelector
	if metricSelector == "" {
		// Fallback to legacy metricId field for backward compatibility
		metricSelector = qm.MetricId
		log.DefaultLogger.Info("Using legacy metricId field", "metricId", qm.MetricId)
		// Add entitySelector as filter if provided (legacy support)
		if qm.EntitySelector != "" {
			metricSelector = fmt.Sprintf("%s:filter(%s)", metricSelector, qm.EntitySelector)
			log.DefaultLogger.Info("Added entitySelector to metricSelector", "entitySelector", qm.EntitySelector)
		}
	}

	log.DefaultLogger.Info("Query model", "metricSelector", metricSelector, "useDashboardTime", qm.UseDashboardTime)

	// Validate metric selector
	if metricSelector == "" {
		return backend.ErrDataResponse(backend.StatusBadRequest, "metricSelector or metricId is required")
	}

	// Determine time range
	var fromMs, toMs int64
	if qm.UseDashboardTime {
		// Use dashboard time range
		fromMs = query.TimeRange.From.UnixMilli()
		toMs = query.TimeRange.To.UnixMilli()
	} else {
		// Use custom time range
		fromMs, err = parseTimestamp(qm.CustomFrom)
		if err != nil {
			return backend.ErrDataResponse(backend.StatusBadRequest, fmt.Sprintf("invalid customFrom: %v", err))
		}
		toMs, err = parseTimestamp(qm.CustomTo)
		if err != nil {
			return backend.ErrDataResponse(backend.StatusBadRequest, fmt.Sprintf("invalid customTo: %v", err))
		}
	}

	// Set default resolution if not provided
	resolution := qm.Resolution
	if resolution == "" {
		resolution = "5m"
	}

	// Query Dynatrace API using /api/v2/metrics/query endpoint
	dynatraceResp, err := d.queryDynatraceAPI(ctx, metricSelector, fromMs, toMs, resolution)
	if err != nil {
		return backend.ErrDataResponse(backend.StatusInternal, fmt.Sprintf("error querying Dynatrace API: %v", err))
	}

	// Convert Dynatrace response to Grafana data frames
	if len(dynatraceResp.Result) == 0 {
		return backend.ErrDataResponse(backend.StatusNotFound, "no data returned from Dynatrace API")
	}

	for _, result := range dynatraceResp.Result {
		for _, dataSet := range result.Data {
			// Log dimensionMap for debugging
			log.DefaultLogger.Info("Processing data", "metricId", result.MetricId, "dimensionMap", dataSet.DimensionMap, "dimensionCount", len(dataSet.DimensionMap))

			// Add value field with labels from dimensionMap
			// Note: dimensionMap can be nil or empty map, both are handled correctly by NewField
			labels := dataSet.DimensionMap
			if labels == nil {
				labels = make(map[string]string)
			}

			// Build frame name and field name based on metric ID and dimensions
			// Use labelChart if specified to create a cleaner name
			frameName := result.MetricId
			fieldName := result.MetricId
			fieldLabels := labels // Labels to attach to the field (keep all by default)

			if len(labels) > 0 {
				if qm.LabelChart != "" && qm.LabelChart != "" {
					// User specified a labelChart field - use only that field for the name
					if labelValue, exists := labels[qm.LabelChart]; exists {
						// Use the specified label value for both frame and field names
						frameName = labelValue
						fieldName = labelValue
						// Don't attach labels to the field to avoid duplication in legend
						fieldLabels = nil
						log.DefaultLogger.Info("Using labelChart field", "labelChart", qm.LabelChart, "value", labelValue)
					} else {
						log.DefaultLogger.Warn("Label field not found in dimensionMap", "labelChart", qm.LabelChart, "availableLabels", labels)
						// Fallback to default behavior: use all dimension values
						dimensionValues := ""
						for _, value := range labels {
							if dimensionValues != "" {
								dimensionValues += " "
							}
							dimensionValues += value
						}
						fieldName = dimensionValues

						// Build frameName with key=value format
						dimensionLabels := ""
						for key, value := range labels {
							if dimensionLabels != "" {
								dimensionLabels += ", "
							}
							dimensionLabels += fmt.Sprintf("%s=%s", key, value)
						}
						frameName = fmt.Sprintf("%s{%s}", result.MetricId, dimensionLabels)
					}
				} else {
					// Default behavior: use all dimension values in field name
					dimensionValues := ""
					for _, value := range labels {
						if dimensionValues != "" {
							dimensionValues += " "
						}
						dimensionValues += value
					}
					fieldName = dimensionValues

					// Build frameName with key=value format
					dimensionLabels := ""
					for key, value := range labels {
						if dimensionLabels != "" {
							dimensionLabels += ", "
						}
						dimensionLabels += fmt.Sprintf("%s=%s", key, value)
					}
					frameName = fmt.Sprintf("%s{%s}", result.MetricId, dimensionLabels)
				}
			}

			// Create data frame with descriptive name
			frame := data.NewFrame(frameName)

			// Convert timestamps to time.Time
			times := make([]time.Time, len(dataSet.Timestamps))
			for i, ts := range dataSet.Timestamps {
				times[i] = time.UnixMilli(ts)
			}

			// Add time field
			frame.Fields = append(frame.Fields, data.NewField("time", nil, times))

			log.DefaultLogger.Info("Creating value field", "labels", fieldLabels, "fieldName", fieldName, "frameName", frameName)
			valueField := data.NewField(fieldName, fieldLabels, dataSet.Values)
			frame.Fields = append(frame.Fields, valueField)

			// Add metadata for better visualization
			frame.Meta = &data.FrameMeta{
				ExecutedQueryString: fmt.Sprintf("Metric: %s, Resolution: %s", result.MetricId, resolution),
			}

			// Add the frame to the response
			response.Frames = append(response.Frames, frame)
		}
	}

	return response
}

// queryDynatraceAPI queries the Dynatrace Metrics V2 API using /api/v2/metrics/query endpoint
func (d *Datasource) queryDynatraceAPI(ctx context.Context, metricSelector string, fromMs, toMs int64, resolution string) (*DynatraceMetricsResponse, error) {
	// Build URL for /api/v2/metrics/query endpoint with proper URL encoding
	baseUrl := fmt.Sprintf("%s/api/v2/metrics/query", d.apiUrl)

	// Create URL with query parameters
	params := url.Values{}
	params.Add("metricSelector", metricSelector)
	params.Add("from", fmt.Sprintf("%d", fromMs))
	params.Add("to", fmt.Sprintf("%d", toMs))
	params.Add("resolution", resolution)

	fullUrl := fmt.Sprintf("%s?%s", baseUrl, params.Encode())

	log.DefaultLogger.Info("Querying Dynatrace API", "url", fullUrl)

	// Create request
	req, err := http.NewRequestWithContext(ctx, "GET", fullUrl, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}

	// Add authentication header
	req.Header.Set("Authorization", fmt.Sprintf("Api-Token %s", d.apiToken))
	req.Header.Set("Content-Type", "application/json")

	// Create HTTP client with TLS configuration
	client, err := d.createHTTPClient()
	if err != nil {
		return nil, fmt.Errorf("error creating HTTP client: %w", err)
	}

	// Execute request
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error executing request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Dynatrace API returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	var dynatraceResp DynatraceMetricsResponse
	if err := json.NewDecoder(resp.Body).Decode(&dynatraceResp); err != nil {
		return nil, fmt.Errorf("error decoding response: %w", err)
	}

	log.DefaultLogger.Info("Dynatrace API response", "totalCount", dynatraceResp.TotalCount, "results", len(dynatraceResp.Result))

	return &dynatraceResp, nil
}

// createHTTPClient creates an HTTP client with TLS configuration
func (d *Datasource) createHTTPClient() (*http.Client, error) {
	// Create TLS config
	tlsConfig := &tls.Config{}

	// Skip TLS verification if configured
	if d.tlsSkipVerify {
		log.DefaultLogger.Warn("TLS certificate verification is disabled - this is insecure!")
		tlsConfig.InsecureSkipVerify = true
	} else if d.tlsCertificate != "" {
		// Load custom certificate
		certPool := x509.NewCertPool()
		if !certPool.AppendCertsFromPEM([]byte(d.tlsCertificate)) {
			return nil, fmt.Errorf("failed to parse TLS certificate")
		}
		tlsConfig.RootCAs = certPool
		log.DefaultLogger.Info("Using custom TLS certificate")
	}

	// Create transport with TLS config
	transport := &http.Transport{
		TLSClientConfig: tlsConfig,
	}

	// Create HTTP client
	client := &http.Client{
		Timeout:   30 * time.Second,
		Transport: transport,
	}

	return client, nil
}

// parseTimestamp converts a timestamp string to milliseconds
// Supports both milliseconds and relative times (e.g., "now-1h")
func parseTimestamp(ts string) (int64, error) {
	if ts == "" {
		return time.Now().UnixMilli(), nil
	}

	// Try to parse as milliseconds
	if msec, err := strconv.ParseInt(ts, 10, 64); err == nil {
		return msec, nil
	}

	// TODO: Add support for relative times (now-1h, etc.)
	// For now, just return current time
	return time.Now().UnixMilli(), nil
}

// CheckHealth handles health checks sent from Grafana to the plugin.
// The main use case for these health checks is the test button on the
// datasource configuration page which allows users to verify that
// a datasource is working as expected.
func (d *Datasource) CheckHealth(ctx context.Context, req *backend.CheckHealthRequest) (*backend.CheckHealthResult, error) {
	log.DefaultLogger.Info("CheckHealth called")

	// Validate configuration
	if d.apiUrl == "" {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: "API URL is not configured",
		}, nil
	}

	if d.apiToken == "" {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: "API Token is not configured",
		}, nil
	}

	// Test connection by querying the /health endpoint
	url := fmt.Sprintf("%s/health", d.apiUrl)
	reqHttp, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: fmt.Sprintf("Error creating health check request: %v", err),
		}, nil
	}

	// Create HTTP client with TLS configuration
	client, err := d.createHTTPClient()
	if err != nil {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: fmt.Sprintf("Error creating HTTP client: %v", err),
		}, nil
	}

	resp, err := client.Do(reqHttp)
	if err != nil {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: fmt.Sprintf("Error connecting to Dynatrace API: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: fmt.Sprintf("Dynatrace API health check failed (status %d): %s", resp.StatusCode, string(body)),
		}, nil
	}

	return &backend.CheckHealthResult{
		Status:  backend.HealthStatusOk,
		Message: "Successfully connected to Dynatrace API",
	}, nil
}
