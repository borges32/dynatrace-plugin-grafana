package plugin

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/grafana/grafana-plugin-sdk-go/backend"
	"github.com/grafana/grafana-plugin-sdk-go/backend/log"
	"github.com/grafana/grafana-plugin-sdk-go/data"
)

// DynatraceLogsResponse models the response of POST /api/v2/logs/search.
type DynatraceLogsResponse struct {
	TotalCount int                      `json:"totalCount"`
	SliceSize  int                      `json:"sliceSize"`
	SliceStart int                      `json:"sliceStart"`
	Results    []map[string]interface{} `json:"results"`
}

// queryLogs runs a Dynatrace log search and returns a Grafana data frame
// formatted as a Loki-compatible logs frame, so the standard Grafana Logs
// panel can render it without any additional configuration.
//
// A Loki logs frame contains three fields:
//   - "labels"   (json.RawMessage) - per-line label set
//   - "Time"     (time.Time)       - timestamp
//   - "Line"     (string)          - the actual log content
//   - "tsNs"     (string)          - timestamp in nanoseconds (used for ordering)
//   - "id"       (string)          - unique line id (for de-duplication)
//
// Frame meta is tagged with FrameMeta.PreferredVisualization = VisTypeLogs.
func (d *Datasource) queryLogs(ctx context.Context, qm queryModel, q backend.DataQuery) backend.DataResponse {
	// Resolve time range
	var fromMs, toMs int64
	var err error
	if qm.UseDashboardTime || (qm.CustomFrom == "" && qm.CustomTo == "") {
		fromMs = q.TimeRange.From.UnixMilli()
		toMs = q.TimeRange.To.UnixMilli()
	} else {
		fromMs, err = parseTimestamp(qm.CustomFrom)
		if err != nil {
			return backend.ErrDataResponse(backend.StatusBadRequest, fmt.Sprintf("invalid customFrom: %v", err))
		}
		toMs, err = parseTimestamp(qm.CustomTo)
		if err != nil {
			return backend.ErrDataResponse(backend.StatusBadRequest, fmt.Sprintf("invalid customTo: %v", err))
		}
	}

	limit := qm.LogLimit
	if limit <= 0 {
		limit = 1000
	}

	logsResp, err := d.queryDynatraceLogsAPI(ctx, qm.LogQuery, fromMs, toMs, limit)
	if err != nil {
		return backend.ErrDataResponse(backend.StatusInternal, fmt.Sprintf("error querying Dynatrace logs API: %v", err))
	}

	return logsToLokiFrame(logsResp, qm.LogQuery)
}

// queryDynatraceLogsAPI calls GET /api/v2/logs/search on the configured
// Dynatrace tenant (or simulator).
func (d *Datasource) queryDynatraceLogsAPI(ctx context.Context, logQuery string, fromMs, toMs int64, limit int) (*DynatraceLogsResponse, error) {
	baseUrl := fmt.Sprintf("%s/api/v2/logs/search", d.apiUrl)

	params := url.Values{}
	if logQuery != "" {
		params.Add("query", logQuery)
	}
	params.Add("from", strconv.FormatInt(fromMs, 10))
	params.Add("to", strconv.FormatInt(toMs, 10))
	params.Add("limit", strconv.Itoa(limit))
	params.Add("sort", "desc")

	fullUrl := fmt.Sprintf("%s?%s", baseUrl, params.Encode())
	log.DefaultLogger.Info("Querying Dynatrace logs API", "url", fullUrl)

	req, err := http.NewRequestWithContext(ctx, "GET", fullUrl, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Api-Token %s", d.apiToken))
	req.Header.Set("Content-Type", "application/json")

	client, err := d.createHTTPClient()
	if err != nil {
		return nil, fmt.Errorf("error creating HTTP client: %w", err)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error executing request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Dynatrace logs API returned status %d: %s", resp.StatusCode, string(body))
	}

	var out DynatraceLogsResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("error decoding logs response: %w", err)
	}
	log.DefaultLogger.Info("Dynatrace logs API response", "totalCount", out.TotalCount, "returned", len(out.Results))
	return &out, nil
}

// logsToLokiFrame converts Dynatrace log records to a Grafana data frame
// that matches the Loki logs frame format (so Grafana renders it with the
// Logs panel automatically).
func logsToLokiFrame(resp *DynatraceLogsResponse, query string) backend.DataResponse {
	var response backend.DataResponse

	n := len(resp.Results)
	labelsField := make([]json.RawMessage, n)
	timeField := make([]time.Time, n)
	lineField := make([]string, n)
	tsNsField := make([]string, n)
	idField := make([]string, n)

	for i, rec := range resp.Results {
		// timestamp
		var ts time.Time
		if v, ok := rec["timestamp"].(string); ok {
			if parsed, err := time.Parse(time.RFC3339Nano, v); err == nil {
				ts = parsed
			}
		}
		timeField[i] = ts
		tsNsField[i] = strconv.FormatInt(ts.UnixNano(), 10)

		// content / line
		line := ""
		if v, ok := rec["content"].(string); ok {
			line = v
		}
		lineField[i] = line

		// labels: every record field except `timestamp` and `content`
		lbls := make(map[string]string, len(rec))
		for k, v := range rec {
			if k == "timestamp" || k == "content" {
				continue
			}
			lbls[k] = fmt.Sprintf("%v", v)
		}
		if raw, err := json.Marshal(lbls); err == nil {
			labelsField[i] = raw
		} else {
			labelsField[i] = json.RawMessage("{}")
		}

		// stable id: nanos + short hash of line
		idField[i] = fmt.Sprintf("%s_%d", tsNsField[i], i)
	}

	frame := data.NewFrame("logs",
		data.NewField("labels", nil, labelsField),
		data.NewField("Time", nil, timeField),
		data.NewField("Line", nil, lineField),
		data.NewField("tsNs", nil, tsNsField),
		data.NewField("id", nil, idField),
	)

	frame.Meta = &data.FrameMeta{
		PreferredVisualization: data.VisTypeLogs,
		ExecutedQueryString:    fmt.Sprintf("logs query: %q", query),
	}

	response.Frames = append(response.Frames, frame)
	return response
}
