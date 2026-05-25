package plugin

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/grafana/grafana-plugin-sdk-go/backend"
	"github.com/grafana/grafana-plugin-sdk-go/backend/log"
	"github.com/grafana/grafana-plugin-sdk-go/data"
)

// Dynatrace Grail DQL has an async API:
//   1. POST /platform/storage/query/v1/query:execute     -> { requestToken, state: RUNNING }
//   2. GET  /platform/storage/query/v1/query:poll?...    -> { state: SUCCEEDED, result: {...} }
//
// This handler hides the polling loop and returns a Loki-formatted frame.

const (
	grailExecutePath   = "/platform/storage/query/v1/query:execute"
	grailPollPath      = "/platform/storage/query/v1/query:poll"
	grailPollMaxWait   = 60 * time.Second // total polling budget
	grailPollInterval  = 500 * time.Millisecond
)

type grailExecuteRequest struct {
	Query                 string `json:"query"`
	DefaultTimeframeStart string `json:"defaultTimeframeStart,omitempty"`
	DefaultTimeframeEnd   string `json:"defaultTimeframeEnd,omitempty"`
	MaxResultRecords      int    `json:"maxResultRecords,omitempty"`
}

type grailExecuteResponse struct {
	State        string `json:"state"`
	RequestToken string `json:"requestToken"`
}

type grailPollResponse struct {
	State  string `json:"state"`
	Error  *struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"error,omitempty"`
	Result *grailResult `json:"result,omitempty"`
}

type grailResult struct {
	Records []map[string]interface{} `json:"records"`
	Types   []map[string]interface{} `json:"types"`
}

func (d *Datasource) queryDqlGrail(ctx context.Context, qm queryModel, q backend.DataQuery) backend.DataResponse {
	if strings.TrimSpace(qm.DqlQuery) == "" {
		return backend.ErrDataResponse(backend.StatusBadRequest, "dqlQuery is required")
	}

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

	limit := qm.DqlLimit
	if limit <= 0 {
		limit = 1000
	}

	result, err := d.executeGrailDQL(ctx, qm.DqlQuery, fromMs, toMs, limit)
	if err != nil {
		return backend.ErrDataResponse(backend.StatusInternal, fmt.Sprintf("error executing Grail DQL: %v", err))
	}

	return grailRecordsToLokiFrame(result.Records, qm.DqlQuery)
}

// executeGrailDQL submits the query and polls until it finishes (or the budget runs out).
func (d *Datasource) executeGrailDQL(ctx context.Context, query string, fromMs, toMs int64, limit int) (*grailResult, error) {
	client, err := d.createHTTPClient()
	if err != nil {
		return nil, fmt.Errorf("error creating HTTP client: %w", err)
	}

	body := grailExecuteRequest{
		Query:                 query,
		DefaultTimeframeStart: time.UnixMilli(fromMs).UTC().Format(time.RFC3339Nano),
		DefaultTimeframeEnd:   time.UnixMilli(toMs).UTC().Format(time.RFC3339Nano),
		MaxResultRecords:      limit,
	}
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("error marshaling Grail request: %w", err)
	}

	execURL := d.grailBaseURL() + grailExecutePath
	log.DefaultLogger.Info("Submitting Grail DQL", "url", execURL, "query", query)

	req, err := http.NewRequestWithContext(ctx, "POST", execURL, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}
	d.applyAuth(req)
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error executing request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		raw, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Grail query:execute returned status %d: %s", resp.StatusCode, string(raw))
	}

	var execResp grailExecuteResponse
	if err := json.NewDecoder(resp.Body).Decode(&execResp); err != nil {
		return nil, fmt.Errorf("error decoding execute response: %w", err)
	}
	if execResp.RequestToken == "" {
		return nil, fmt.Errorf("Grail response missing requestToken")
	}

	// Poll loop.
	deadline := time.Now().Add(grailPollMaxWait)
	// The requestToken is base64-ish and frequently contains '+', '/' and '='.
	// Concatenating it raw into a query string turns '+' into a literal space
	// per application/x-www-form-urlencoded — Dynatrace then rejects with
	// "INVALID_REQUEST_TOKEN_PROVIDED". Use url.Values so each special char
	// is correctly percent-encoded.
	pollParams := url.Values{}
	pollParams.Set("request-token", execResp.RequestToken)
	pollURL := fmt.Sprintf("%s%s?%s", d.grailBaseURL(), grailPollPath, pollParams.Encode())
	for {
		pollResp, err := d.pollGrail(ctx, client, pollURL)
		if err != nil {
			return nil, err
		}

		switch pollResp.State {
		case "SUCCEEDED":
			if pollResp.Result == nil {
				return &grailResult{}, nil
			}
			return pollResp.Result, nil
		case "FAILED":
			if pollResp.Error != nil {
				return nil, fmt.Errorf("Grail query failed (code %d): %s", pollResp.Error.Code, pollResp.Error.Message)
			}
			return nil, fmt.Errorf("Grail query failed")
		case "CANCELLED":
			return nil, fmt.Errorf("Grail query was cancelled")
		default:
			// RUNNING, NOT_STARTED, etc. — keep polling.
		}

		if time.Now().After(deadline) {
			return nil, fmt.Errorf("Grail query timed out after %s (state=%s)", grailPollMaxWait, pollResp.State)
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(grailPollInterval):
		}
	}
}

func (d *Datasource) pollGrail(ctx context.Context, client *http.Client, pollURL string) (*grailPollResponse, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", pollURL, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating poll request: %w", err)
	}
	d.applyAuth(req)

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error executing poll request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Grail query:poll returned status %d: %s", resp.StatusCode, string(raw))
	}
	var out grailPollResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("error decoding poll response: %w", err)
	}
	return &out, nil
}

// grailRecordsToLokiFrame converts the heterogeneous Grail records to a Loki
// logs frame so any Grafana Logs panel can render the response.
//
// The mapping is:
//   - timestamp / startTime / event.start                -> Time
//   - content / message / body                           -> Line
//   - every other field                                  -> labels
//
// When the records don't have a recognizable "content" column (e.g. results
// of `summarize count() by ...`) the entire record is serialized as JSON in
// the Line field, so aggregated DQL results still display usefully.
func grailRecordsToLokiFrame(records []map[string]interface{}, query string) backend.DataResponse {
	var response backend.DataResponse

	n := len(records)
	labelsField := make([]json.RawMessage, n)
	timeField := make([]time.Time, n)
	lineField := make([]string, n)
	tsNsField := make([]string, n)
	idField := make([]string, n)

	for i, rec := range records {
		ts := extractTimestamp(rec)
		timeField[i] = ts
		tsNsField[i] = strconv.FormatInt(ts.UnixNano(), 10)

		line, hasLine := extractLine(rec)
		if !hasLine {
			// Aggregated record without a body -> serialize whole record.
			if raw, err := json.Marshal(rec); err == nil {
				line = string(raw)
			}
		}
		lineField[i] = line

		labels := make(map[string]string)
		for k, v := range rec {
			if isTimestampKey(k) || isContentKey(k) {
				continue
			}
			labels[k] = fmt.Sprintf("%v", v)
		}
		if raw, err := json.Marshal(labels); err == nil {
			labelsField[i] = raw
		} else {
			labelsField[i] = json.RawMessage("{}")
		}

		idField[i] = fmt.Sprintf("%s_%d", tsNsField[i], i)
	}

	frame := data.NewFrame("dql",
		data.NewField("labels", nil, labelsField),
		data.NewField("Time", nil, timeField),
		data.NewField("Line", nil, lineField),
		data.NewField("tsNs", nil, tsNsField),
		data.NewField("id", nil, idField),
	)
	frame.Meta = &data.FrameMeta{
		PreferredVisualization: data.VisTypeLogs,
		ExecutedQueryString:    fmt.Sprintf("dql: %s", query),
	}
	response.Frames = append(response.Frames, frame)
	return response
}

func extractTimestamp(rec map[string]interface{}) time.Time {
	for _, k := range []string{"timestamp", "startTime", "start_time", "event.start", "@timestamp"} {
		if v, ok := rec[k]; ok {
			if t := parseAnyTimestamp(v); !t.IsZero() {
				return t
			}
		}
	}
	return time.Time{}
}

func extractLine(rec map[string]interface{}) (string, bool) {
	for _, k := range []string{"content", "message", "body", "log"} {
		if v, ok := rec[k]; ok {
			if s, ok := v.(string); ok && s != "" {
				return s, true
			}
		}
	}
	return "", false
}

func isTimestampKey(k string) bool {
	switch k {
	case "timestamp", "startTime", "start_time", "event.start", "@timestamp":
		return true
	}
	return false
}

func isContentKey(k string) bool {
	switch k {
	case "content", "message", "body", "log":
		return true
	}
	return false
}

func parseAnyTimestamp(v interface{}) time.Time {
	switch t := v.(type) {
	case string:
		if parsed, err := time.Parse(time.RFC3339Nano, t); err == nil {
			return parsed
		}
		if ms, err := strconv.ParseInt(t, 10, 64); err == nil {
			return time.UnixMilli(ms)
		}
	case float64:
		return time.UnixMilli(int64(t))
	case int64:
		return time.UnixMilli(t)
	case int:
		return time.UnixMilli(int64(t))
	}
	return time.Time{}
}
