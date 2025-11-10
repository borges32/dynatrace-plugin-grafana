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
from mock_data import METRICS, get_mock_data_points

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


@app.route('/api/v2/metrics/query', methods=['POST'])
@require_api_token
def query_metrics():
    """
    Query metrics with POST method (alternative endpoint)
    """
    data = request.get_json()
    metric_selector = data.get('metricSelector', '')
    from_param = data.get('from')
    to_param = data.get('to', int(time.time() * 1000))
    resolution = data.get('resolution', '1m')
    
    if not from_param:
        return jsonify({
            "error": {
                "code": 400,
                "message": "Missing required parameter 'from'"
            }
        }), 400
    
    # Simplified - return data for first matching metric
    matching_metric = next((m for m in METRICS if metric_selector in m['metricId']), None)
    
    if not matching_metric:
        return jsonify({
            "error": {
                "code": 404,
                "message": f"No metrics found matching selector '{metric_selector}'"
            }
        }), 404
    
    data_points = get_mock_data_points(
        matching_metric['metricId'], 
        from_param, 
        to_param, 
        resolution
    )
    
    response = {
        "totalCount": 1,
        "nextPageKey": None,
        "resolution": resolution,
        "result": [
            {
                "metricId": matching_metric['metricId'],
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
            "query_metrics": "POST /api/v2/metrics/query",
            "health": "GET /health"
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
    print("  POST /api/v2/metrics/query - Query metrics")
    print("  GET  /health - Health check")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=8080, debug=True)
