package plugin

import (
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

// DynatraceProblem mirrors the relevant subset of a problem record
// returned by GET /api/v2/problems.
type DynatraceProblem struct {
	ProblemID        string                   `json:"problemId"`
	DisplayID        string                   `json:"displayId"`
	Title            string                   `json:"title"`
	Status           string                   `json:"status"`
	SeverityLevel    string                   `json:"severityLevel"`
	ImpactLevel      string                   `json:"impactLevel"`
	StartTime        int64                    `json:"startTime"`
	EndTime          int64                    `json:"endTime"`
	AffectedEntities []map[string]interface{} `json:"affectedEntities"`
	ImpactedEntities []map[string]interface{} `json:"impactedEntities"`
	RootCauseEntity  map[string]interface{}   `json:"rootCauseEntity"`
	ManagementZones  []map[string]interface{} `json:"managementZones"`
	EntityTags       []map[string]interface{} `json:"entityTags"`
}

// DynatraceProblemsResponse mirrors the envelope returned by the API.
type DynatraceProblemsResponse struct {
	TotalCount  int                `json:"totalCount"`
	PageSize    int                `json:"pageSize"`
	NextPageKey *string            `json:"nextPageKey"`
	Problems    []DynatraceProblem `json:"problems"`
}

// queryAlerts calls /api/v2/problems and returns the response as a Grafana
// table frame, with one row per problem. The frame is annotated with
// FrameMeta.PreferredVisualization = VisTypeTable so the Table panel renders
// it directly; the Stat / List panels also work without configuration.
func (d *Datasource) queryAlerts(ctx context.Context, qm queryModel, q backend.DataQuery) backend.DataResponse {
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

	pageSize := qm.AlertPageSize
	if pageSize <= 0 {
		pageSize = 50
	}

	resp, err := d.queryDynatraceAlertsAPI(ctx, qm.AlertSelector, fromMs, toMs, pageSize)
	if err != nil {
		return backend.ErrDataResponse(backend.StatusInternal, fmt.Sprintf("error querying Dynatrace problems API: %v", err))
	}

	return problemsToFrame(resp, qm.AlertSelector)
}

func (d *Datasource) queryDynatraceAlertsAPI(ctx context.Context, selector string, fromMs, toMs int64, pageSize int) (*DynatraceProblemsResponse, error) {
	baseUrl := fmt.Sprintf("%s/api/v2/problems", d.apiUrl)

	params := url.Values{}
	if selector != "" {
		params.Add("problemSelector", selector)
	}
	params.Add("from", strconv.FormatInt(fromMs, 10))
	params.Add("to", strconv.FormatInt(toMs, 10))
	params.Add("pageSize", strconv.Itoa(pageSize))

	fullUrl := fmt.Sprintf("%s?%s", baseUrl, params.Encode())
	log.DefaultLogger.Info("Querying Dynatrace problems API", "url", fullUrl)

	req, err := http.NewRequestWithContext(ctx, "GET", fullUrl, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}
	d.applyAuth(req)
	req.Header.Set("Content-Type", "application/json")

	client, err := d.createHTTPClient()
	if err != nil {
		return nil, fmt.Errorf("error creating HTTP client: %w", err)
	}

	httpResp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error executing request: %w", err)
	}
	defer httpResp.Body.Close()

	if httpResp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(httpResp.Body)
		return nil, fmt.Errorf("Dynatrace problems API returned status %d: %s", httpResp.StatusCode, string(body))
	}

	var out DynatraceProblemsResponse
	if err := json.NewDecoder(httpResp.Body).Decode(&out); err != nil {
		return nil, fmt.Errorf("error decoding problems response: %w", err)
	}
	log.DefaultLogger.Info("Dynatrace problems API response", "totalCount", out.TotalCount, "returned", len(out.Problems))
	return &out, nil
}

// problemsToFrame builds a table-style data frame with one row per problem.
// Columns: startTime, endTime, displayId, status, severityLevel, impactLevel,
// title, managementZones, tags, affectedEntities, problemId.
func problemsToFrame(resp *DynatraceProblemsResponse, selector string) backend.DataResponse {
	var response backend.DataResponse

	n := len(resp.Problems)
	startTimes := make([]time.Time, n)
	endTimes := make([]*time.Time, n)
	displayIds := make([]string, n)
	statuses := make([]string, n)
	severities := make([]string, n)
	impacts := make([]string, n)
	titles := make([]string, n)
	mZones := make([]string, n)
	tags := make([]string, n)
	affected := make([]string, n)
	problemIds := make([]string, n)

	for i, p := range resp.Problems {
		startTimes[i] = time.UnixMilli(p.StartTime)
		if p.EndTime > 0 {
			end := time.UnixMilli(p.EndTime)
			endTimes[i] = &end
		}
		displayIds[i] = p.DisplayID
		statuses[i] = p.Status
		severities[i] = p.SeverityLevel
		impacts[i] = p.ImpactLevel
		titles[i] = p.Title
		mZones[i] = joinMaps(p.ManagementZones, "name", ", ")
		tags[i] = joinTags(p.EntityTags)
		affected[i] = joinEntities(p.AffectedEntities)
		problemIds[i] = p.ProblemID
	}

	frame := data.NewFrame("problems",
		data.NewField("startTime", nil, startTimes),
		data.NewField("endTime", nil, endTimes),
		data.NewField("displayId", nil, displayIds),
		data.NewField("status", nil, statuses),
		data.NewField("severityLevel", nil, severities),
		data.NewField("impactLevel", nil, impacts),
		data.NewField("title", nil, titles),
		data.NewField("managementZones", nil, mZones),
		data.NewField("tags", nil, tags),
		data.NewField("affectedEntities", nil, affected),
		data.NewField("problemId", nil, problemIds),
	)

	frame.Meta = &data.FrameMeta{
		PreferredVisualization: data.VisTypeTable,
		ExecutedQueryString:    fmt.Sprintf("problemSelector: %q", selector),
	}
	response.Frames = append(response.Frames, frame)
	return response
}

// joinMaps extracts `key` from each map and joins with `sep`.
func joinMaps(items []map[string]interface{}, key, sep string) string {
	parts := make([]string, 0, len(items))
	for _, m := range items {
		if v, ok := m[key]; ok {
			parts = append(parts, fmt.Sprintf("%v", v))
		}
	}
	return strings.Join(parts, sep)
}

func joinTags(items []map[string]interface{}) string {
	parts := make([]string, 0, len(items))
	for _, m := range items {
		if s, ok := m["stringRepresentation"].(string); ok {
			parts = append(parts, s)
			continue
		}
		k, _ := m["key"].(string)
		v, _ := m["value"].(string)
		if k != "" {
			parts = append(parts, fmt.Sprintf("%s:%s", k, v))
		}
	}
	return strings.Join(parts, ", ")
}

func joinEntities(items []map[string]interface{}) string {
	parts := make([]string, 0, len(items))
	for _, m := range items {
		if name, ok := m["name"].(string); ok && name != "" {
			parts = append(parts, name)
		}
	}
	return strings.Join(parts, ", ")
}
