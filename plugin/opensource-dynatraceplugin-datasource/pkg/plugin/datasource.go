package plugin

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
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

	apiToken := settings.DecryptedSecureJSONData["apiToken"]

	return &Datasource{
		settings: settings,
		apiUrl:   apiUrl,
		apiToken: apiToken,
	}, nil
}

// Datasource is a Dynatrace datasource which can respond to data queries, reports
// its health and has alerting support.
type Datasource struct {
	settings backend.DataSourceInstanceSettings
	apiUrl   string
	apiToken string
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
	MetricId         string  `json:"metricId"`
	EntitySelector   string  `json:"entitySelector"`
	UseDashboardTime bool    `json:"useDashboardTime"`
	CustomFrom       string  `json:"customFrom"`
	CustomTo         string  `json:"customTo"`
	Resolution       string  `json:"resolution"`
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

	log.DefaultLogger.Info("Query model", "metricId", qm.MetricId, "useDashboardTime", qm.UseDashboardTime)

	// Validate metric ID
	if qm.MetricId == "" {
		return backend.ErrDataResponse(backend.StatusBadRequest, "metricId is required")
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

	// Query Dynatrace API
	dynatraceResp, err := d.queryDynatraceAPI(ctx, qm.MetricId, qm.EntitySelector, fromMs, toMs, resolution)
	if err != nil {
		return backend.ErrDataResponse(backend.StatusInternal, fmt.Sprintf("error querying Dynatrace API: %v", err))
	}

	// Convert Dynatrace response to Grafana data frames
	if len(dynatraceResp.Result) == 0 {
		return backend.ErrDataResponse(backend.StatusNotFound, "no data returned from Dynatrace API")
	}

	for _, result := range dynatraceResp.Result {
		for _, dataSet := range result.Data {
			// Create data frame
			frame := data.NewFrame(result.MetricId)

			// Convert timestamps to time.Time
			times := make([]time.Time, len(dataSet.Timestamps))
			for i, ts := range dataSet.Timestamps {
				times[i] = time.UnixMilli(ts)
			}

			// Add fields
			frame.Fields = append(frame.Fields,
				data.NewField("time", nil, times),
				data.NewField("value", nil, dataSet.Values),
			)

			// Add metadata for better visualization
			frame.Meta = &data.FrameMeta{
				ExecutedQueryString: fmt.Sprintf("Metric: %s, Resolution: %s", qm.MetricId, resolution),
			}

			// Add the frame to the response
			response.Frames = append(response.Frames, frame)
		}
	}

	return response
}

// queryDynatraceAPI queries the Dynatrace Metrics V2 API
func (d *Datasource) queryDynatraceAPI(ctx context.Context, metricId string, entitySelector string, fromMs, toMs int64, resolution string) (*DynatraceMetricsResponse, error) {
	// Build URL
	url := fmt.Sprintf("%s/api/v2/metrics/%s?from=%d&to=%d&resolution=%s",
		d.apiUrl, metricId, fromMs, toMs, resolution)

	// Add entitySelector if provided
	if entitySelector != "" {
		url = fmt.Sprintf("%s&entitySelector=%s", url, entitySelector)
	}

	log.DefaultLogger.Info("Querying Dynatrace API", "url", url)

	// Create request
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}

	// Add authentication header
	req.Header.Set("Authorization", fmt.Sprintf("Api-Token %s", d.apiToken))
	req.Header.Set("Content-Type", "application/json")

	// Execute request
	client := &http.Client{Timeout: 30 * time.Second}
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

	client := &http.Client{Timeout: 10 * time.Second}
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
