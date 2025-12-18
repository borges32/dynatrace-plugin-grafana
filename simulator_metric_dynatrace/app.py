"""
Dynatrace Metrics V2 API Simulator
Simulates the following endpoints:
- GET /api/v2/metrics - List metrics
- GET /api/v2/metrics/{metricId} - Get data points
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import time
import os
from mock_data import METRICS, get_mock_data_points, get_mock_multi_series_data

app = Flask(__name__)
CORS(app)

# Valid API tokens for the simulator (can be configured via environment variable)
VALID_API_TOKENS = os.getenv('DT_API_TOKENS', 'dt0c01.sample.token1,dt0c01.sample.token2,test-token').split(',')


def require_api_token(f):
    """
    Decorator to validate Dynatrace API Token authentication
    Expects: Authorization: Api-Token {token}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        # Check if Authorization header is present
        if not auth_header:
            return jsonify({
                "error": {
                    "code": 401,
                    "message": "Missing Authorization header. Expected format: 'Api-Token {token}'"
                }
            }), 401
        
        # Check format: "Api-Token {token}"
        parts = auth_header.split(' ', 1)
        if len(parts) != 2 or parts[0] != 'Api-Token':
            return jsonify({
                "error": {
                    "code": 401,
                    "message": "Invalid Authorization header format. Expected format: 'Api-Token {token}'"
                }
            }), 401
        
        token = parts[1]
        
        # Validate token
        if token not in VALID_API_TOKENS:
            return jsonify({
                "error": {
                    "code": 401,
                    "message": "Invalid API token"
                }
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


@app.route('/api/v2/metrics', methods=['GET'])
@require_api_token
def list_metrics():
    """
    List all available metrics
    Query parameters:
    - metricSelector: Filter metrics by selector (optional)
    - text: Filter metrics by text search (optional)
    - fields: Specify fields to return (optional)
    - pageSize: Number of results per page (default: 500)
    - nextPageKey: Key for pagination (optional)
    """
    metric_selector = request.args.get('metricSelector', '')
    text_filter = request.args.get('text', '')
    fields = request.args.get('fields', '+unit,+description,+aggregationTypes,+defaultAggregation,+dimensionDefinitions,+entityType')
    page_size = int(request.args.get('pageSize', 500))
    
    # Filter metrics based on parameters
    filtered_metrics = METRICS.copy()
    
    # Apply text filter if provided
    if text_filter:
        filtered_metrics = [
            m for m in filtered_metrics 
            if text_filter.lower() in m['metricId'].lower() 
            or text_filter.lower() in m['displayName'].lower()
        ]
    
    # Apply metric selector filter (simplified)
    if metric_selector:
        # Simple implementation - check if metric ID contains the selector
        filtered_metrics = [
            m for m in filtered_metrics 
            if metric_selector in m['metricId']
        ]
    
    # Apply pagination
    total_count = len(filtered_metrics)
    paginated_metrics = filtered_metrics[:page_size]
    
    response = {
        "totalCount": total_count,
        "nextPageKey": None,  # Simplified - no actual pagination
        "metrics": paginated_metrics
    }
    
    return jsonify(response), 200


@app.route('/api/v2/metrics/query', methods=['GET', 'POST'])
@require_api_token
def query_metrics():
    """
    Query metrics with complex filters (supports both GET and POST)
    
    Query parameters (GET):
    - metricSelector: Metric selector with filters, transformations (required)
      Examples:
        - builtin:apps.other.crashCount.osAndVersion
        - builtin:apps.other.crashCount.osAndVersion:filter(...)
        - builtin:apps.other.crashCount.osAndVersion:filter(...):splitBy():sort(value(auto,descending))
    - from: Start timestamp in milliseconds (optional for some queries)
    - to: End timestamp in milliseconds (optional)
    - resolution: Data resolution (optional)
    - entitySelector: Additional entity filtering (optional)
    
    Body (POST):
    - Same parameters as GET but in JSON format
    """
    # Support both GET and POST methods
    if request.method == 'POST':
        data = request.get_json() or {}
        metric_selector = data.get('metricSelector', '')
        from_param = data.get('from')
        to_param = data.get('to')
        resolution = data.get('resolution', '1m')
        entity_selector = data.get('entitySelector', '')
    else:  # GET
        metric_selector = request.args.get('metricSelector', '')
        from_param = request.args.get('from')
        to_param = request.args.get('to')
        resolution = request.args.get('resolution', '1m')
        entity_selector = request.args.get('entitySelector', '')
    
    # Set defaults
    if not to_param:
        to_param = str(int(time.time() * 1000))
    if not from_param:
        # Default to last hour
        from_param = str(int(time.time() * 1000) - 3600000)
    
    # Parse metric selector to extract base metric ID
    # Format: metricId:filter(...):splitBy(...):sort(...)
    # Need to handle complex metric IDs like "builtin:service.keyRequest.count.total"
    base_metric_id = ''
    if metric_selector:
        # Split by transformation keywords to get the base metric ID
        parts = metric_selector.split(':filter(')
        if len(parts) > 1:
            base_metric_id = parts[0]
        else:
            parts = metric_selector.split(':splitBy(')
            if len(parts) > 1:
                base_metric_id = parts[0]
            else:
                parts = metric_selector.split(':sort(')
                if len(parts) > 1:
                    base_metric_id = parts[0]
                else:
                    # No transformations, use the whole selector
                    base_metric_id = metric_selector
    
    # Extract filter information (simplified parsing)
    has_filter = ':filter(' in metric_selector
    has_split_by = ':splitBy(' in metric_selector
    has_sort = ':sort(' in metric_selector
    
    # Debug logging
    print(f"[DEBUG] Metric selector: {metric_selector}")
    print(f"[DEBUG] Base metric ID: {base_metric_id}")
    print(f"[DEBUG] Has splitBy: {has_split_by}")
    
    # Find matching metric
    matching_metric = None
    if base_metric_id:
        matching_metric = next((m for m in METRICS if m['metricId'] == base_metric_id), None)
    
    # If exact match not found, try partial match
    if not matching_metric and base_metric_id:
        matching_metric = next((m for m in METRICS if base_metric_id in m['metricId']), None)
    
    # If still not found, use first metric as fallback
    if not matching_metric:
        matching_metric = METRICS[0] if METRICS else None
    
    print(f"[DEBUG] Matching metric: {matching_metric['metricId'] if matching_metric else 'None'}")
    
    if not matching_metric:
        return jsonify({
            "error": {
                "code": 404,
                "message": f"No metrics found matching selector '{metric_selector}'"
            }
        }), 404
    
    # Build response - format depends on transformations
    if has_split_by:
        # When splitBy is used, return data with dimensions (multiple series)
        series_data = get_mock_multi_series_data(
            matching_metric['metricId'], 
            int(from_param), 
            int(to_param), 
            resolution
        )
        
        response = {
            "totalCount": len(series_data),
            "nextPageKey": None,
            "resolution": resolution,
            "result": [
                {
                    "metricId": base_metric_id or matching_metric['metricId'],
                    "dataPointCountRatio": 1.0,
                    "dimensionCountRatio": 1.0,
                    "data": series_data
                }
            ]
        }
    else:
        # Standard response without dimensions (single series)
        data_points = get_mock_data_points(
            matching_metric['metricId'], 
            int(from_param), 
            int(to_param), 
            resolution
        )
        
        response = {
            "totalCount": 1,
            "nextPageKey": None,
            "resolution": resolution,
            "result": [
                {
                    "metricId": base_metric_id or matching_metric['metricId'],
                    "dataPointCountRatio": 1.0,
                    "dimensionCountRatio": 1.0,
                    "data": [
                        {
                            "dimensions": [],
                            "dimensionMap": {},
                            "timestamps": [dp[0] for dp in data_points],
                            "values": [dp[1] for dp in data_points]
                        }
                    ]
                }
            ]
        }
    
    return jsonify(response), 200


@app.route('/api/v2/metrics/<path:metric_id>', methods=['GET'])
@require_api_token
def get_metric_data_points(metric_id):
    """
    Get data points for a specific metric
    Query parameters:
    - from: Start timestamp in milliseconds (required)
    - to: End timestamp in milliseconds (optional, defaults to now)
    - resolution: Data resolution (e.g., "1m", "5m", "1h") (optional)
    - entitySelector: Filter by entities (optional)
    - metricSelector: Additional metric filtering (optional)
    """
    # Get query parameters
    from_param = request.args.get('from')
    to_param = request.args.get('to', str(int(time.time() * 1000)))
    resolution = request.args.get('resolution', '1m')
    entity_selector = request.args.get('entitySelector', '')
    
    # Validate required parameters
    if not from_param:
        return jsonify({
            "error": {
                "code": 400,
                "message": "Missing required parameter 'from'"
            }
        }), 400
    
    # Find the metric
    metric = next((m for m in METRICS if m['metricId'] == metric_id), None)
    
    if not metric:
        return jsonify({
            "error": {
                "code": 404,
                "message": f"Metric '{metric_id}' not found"
            }
        }), 404
    
    # Generate mock data points
    data_points = get_mock_data_points(
        metric_id, 
        int(from_param), 
        int(to_param), 
        resolution
    )
    
    # Build response based on Dynatrace API format
    response = {
        "totalCount": 1,
        "nextPageKey": None,
        "resolution": resolution,
        "result": [
            {
                "metricId": metric_id,
                "dataPointCountRatio": 1.0,
                "dimensionCountRatio": 1.0,
                "data": [
                    {
                        "dimensions": [],
                        "dimensionMap": {},
                        "timestamps": [dp[0] for dp in data_points],
                        "values": [dp[1] for dp in data_points]
                    }
                ]
            }
        ]
    }
    
    return jsonify(response), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Dynatrace API Simulator is running"}), 200


@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information"""
    return jsonify({
        "name": "Dynatrace Metrics V2 API Simulator",
        "version": "1.0.0",
        "endpoints": {
            "list_metrics": "GET /api/v2/metrics",
            "get_metric_data": "GET /api/v2/metrics/{metricId}",
            "query_metrics": "GET|POST /api/v2/metrics/query",
            "health": "GET /health"
        },
        "examples": {
            "simple_query": "/api/v2/metrics/query?metricSelector=builtin:host.cpu.usage",
            "service_requests": "/api/v2/metrics/query?metricSelector=builtin:service.keyRequest.count.total:filter(and(or(in(\"dt.entity.service_method\",entitySelector(\"type(service_method)\"))))):splitBy(\"dt.entity.service_method\"):sort(value(auto,descending)):limit(20)&resolution=5m",
            "filtered_query": "/api/v2/metrics/query?metricSelector=builtin:apps.other.crashCount.osAndVersion:filter(and(or(in(\"dt.entity.os\",entitySelector(\"type(os)\")))))&from=1699500000000&to=1699503600000",
            "complex_query": "/api/v2/metrics/query?metricSelector=builtin:apps.other.crashCount.osAndVersion:filter(...):splitBy():sort(value(auto,descending))"
        }
    }), 200


if __name__ == '__main__':
    print("=" * 60)
    print("Dynatrace Metrics V2 API Simulator")
    print("=" * 60)
    print("Server running on http://localhost:8080")
    print("\nAvailable endpoints:")
    print("  GET  /api/v2/metrics - List all metrics")
    print("  GET  /api/v2/metrics/{metricId} - Get metric data points")
    print("  GET  /api/v2/metrics/query - Query metrics with filters")
    print("  POST /api/v2/metrics/query - Query metrics (JSON body)")
    print("  GET  /health - Health check")
    print("\nExample queries:")
    print("  1. Simple query:")
    print("     /api/v2/metrics/query?metricSelector=builtin:host.cpu.usage")
    print("\n  2. Service requests with splitBy (multiple series):")
    print("     /api/v2/metrics/query?metricSelector=builtin:service.keyRequest.count.total:splitBy(\"dt.entity.service_method\")&resolution=5m")
    print("\n  3. Complex query with filters:")
    print("     /api/v2/metrics/query?metricSelector=builtin:service.keyRequest.count.total:filter(...):splitBy():sort(value(auto,descending)):limit(20)")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=8080, debug=True)
