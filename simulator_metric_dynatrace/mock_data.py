"""
Mock data for Dynatrace Metrics V2 API simulator
"""

METRICS = [
    {
        "metricId": "builtin:host.cpu.usage",
        "displayName": "CPU usage %",
        "description": "Percentage of CPU used",
        "unit": "Percent",
        "aggregationTypes": ["avg", "min", "max"],
        "transformations": [],
        "defaultAggregation": {
            "type": "avg"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.host",
                "name": "Host",
                "index": 0,
                "type": "ENTITY"
            }
        ],
        "entityType": ["HOST"]
    },
    {
        "metricId": "builtin:host.mem.usage",
        "displayName": "Memory usage %",
        "description": "Percentage of memory used",
        "unit": "Percent",
        "aggregationTypes": ["avg", "min", "max"],
        "transformations": [],
        "defaultAggregation": {
            "type": "avg"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.host",
                "name": "Host",
                "index": 0,
                "type": "ENTITY"
            }
        ],
        "entityType": ["HOST"]
    },
    {
        "metricId": "builtin:service.response.time",
        "displayName": "Response time",
        "description": "Average response time of service",
        "unit": "MicroSecond",
        "aggregationTypes": ["avg", "min", "max", "percentile"],
        "transformations": [],
        "defaultAggregation": {
            "type": "avg"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.service",
                "name": "Service",
                "index": 0,
                "type": "ENTITY"
            }
        ],
        "entityType": ["SERVICE"]
    },
    {
        "metricId": "builtin:service.request.count",
        "displayName": "Request count",
        "description": "Number of requests to service",
        "unit": "Count",
        "aggregationTypes": ["count", "sum", "avg"],
        "transformations": [],
        "defaultAggregation": {
            "type": "count"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.service",
                "name": "Service",
                "index": 0,
                "type": "ENTITY"
            }
        ],
        "entityType": ["SERVICE"]
    },
    {
        "metricId": "builtin:host.disk.avail",
        "displayName": "Available disk space",
        "description": "Available disk space in bytes",
        "unit": "Byte",
        "aggregationTypes": ["avg", "min", "max"],
        "transformations": [],
        "defaultAggregation": {
            "type": "avg"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.host",
                "name": "Host",
                "index": 0,
                "type": "ENTITY"
            },
            {
                "key": "dt.entity.disk",
                "name": "Disk",
                "index": 1,
                "type": "ENTITY"
            }
        ],
        "entityType": ["HOST"]
    },
    {
        "metricId": "builtin:apps.other.crashCount.osAndVersion",
        "displayName": "Crash count by OS and version",
        "description": "Number of application crashes grouped by OS and version",
        "unit": "Count",
        "aggregationTypes": ["count", "sum"],
        "transformations": ["filter", "splitBy", "sort"],
        "defaultAggregation": {
            "type": "count"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.device_application",
                "name": "Mobile Application",
                "index": 0,
                "type": "ENTITY"
            },
            {
                "key": "dt.entity.os",
                "name": "Operating System",
                "index": 1,
                "type": "ENTITY"
            },
            {
                "key": "osVersion",
                "name": "OS Version",
                "index": 2,
                "type": "STRING"
            }
        ],
        "entityType": ["MOBILE_APPLICATION"]
    },
    {
        "metricId": "builtin:service.keyRequest.count.total",
        "displayName": "Key request count",
        "description": "Total count of key service method requests",
        "unit": "Count",
        "aggregationTypes": ["count", "sum"],
        "transformations": ["filter", "splitBy", "sort", "limit"],
        "defaultAggregation": {
            "type": "count"
        },
        "dimensionDefinitions": [
            {
                "key": "dt.entity.service",
                "name": "Service",
                "index": 0,
                "type": "ENTITY"
            },
            {
                "key": "dt.entity.service_method",
                "name": "Service Method",
                "index": 1,
                "type": "ENTITY"
            },
            {
                "key": "dt.entity.service_method.name",
                "name": "Service Method Name",
                "index": 2,
                "type": "STRING"
            }
        ],
        "entityType": ["SERVICE", "SERVICE_METHOD"]
    }
]


def get_mock_data_points(metric_id, from_timestamp, to_timestamp, resolution="1m"):
    """
    Generate mock data points for a given metric
    """
    import random
    import time
    
    # Parse timestamps
    if isinstance(from_timestamp, str):
        from_ts = int(from_timestamp)
    else:
        from_ts = from_timestamp
    
    if isinstance(to_timestamp, str):
        to_ts = int(to_timestamp)
    else:
        to_ts = to_timestamp
    
    # Calculate interval based on resolution
    interval_map = {
        "1m": 60000,
        "5m": 300000,
        "1h": 3600000,
        "1d": 86400000
    }
    interval = interval_map.get(resolution, 60000)
    
    # Generate data points
    data_points = []
    current_ts = from_ts
    
    while current_ts <= to_ts:
        # Generate random values based on metric type
        if "cpu" in metric_id or "mem" in metric_id:
            value = random.uniform(20, 90)
        elif "response.time" in metric_id:
            value = random.uniform(100, 5000)
        elif "request.count" in metric_id or "keyRequest.count" in metric_id:
            value = random.randint(1000, 2800)
        elif "crashCount" in metric_id:
            value = random.randint(0, 50)
        elif "disk" in metric_id:
            value = random.uniform(1000000000, 10000000000)
        else:
            value = random.uniform(0, 100)
        
        data_points.append([current_ts, value])
        current_ts += interval
    
    return data_points


def get_mock_multi_series_data(metric_id, from_timestamp, to_timestamp, resolution="5m"):
    """
    Generate mock data for metrics with multiple series (splitBy)
    Returns data in the format expected by the real Dynatrace API
    """
    import random
    
    # Parse timestamps
    if isinstance(from_timestamp, str):
        from_ts = int(from_timestamp)
    else:
        from_ts = from_timestamp
    
    if isinstance(to_timestamp, str):
        to_ts = int(to_timestamp)
    else:
        to_ts = to_timestamp
    
    # Calculate interval based on resolution
    interval_map = {
        "1m": 60000,
        "5m": 300000,
        "1h": 3600000,
        "1d": 86400000
    }
    interval = interval_map.get(resolution, 300000)
    
    # Generate timestamps
    timestamps = []
    current_ts = from_ts
    while current_ts <= to_ts:
        timestamps.append(current_ts)
        current_ts += interval
    
    # Define mock service methods based on the real dynatrace.json example
    if "keyRequest.count" in metric_id or "service" in metric_id:
        series = [
            {
                "dimensions": ["dt.entity.service_method"],
                "dimensionMap": {
                    "dt.entity.service_method": "SERVICE_METHOD-7B94CA28812AEDEB",
                    "dt.entity.service_method.name": "criarCobrancaPut - bki.cielo.com.br"
                },
                "timestamps": timestamps.copy(),
                "values": [random.randint(2000, 2800) for _ in timestamps]
            },
            {
                "dimensions": ["dt.entity.service_method"],
                "dimensionMap": {
                    "dt.entity.service_method": "SERVICE_METHOD-586B0DAF0DCA0215",
                    "dt.entity.service_method.name": "criarCobrancaPutEmv - IFOOD COM AGENCIA DE RESTAURANTES ONLINE S A:14380200000121"
                },
                "timestamps": timestamps.copy(),
                "values": [random.randint(1000, 1400) for _ in timestamps]
            },
            {
                "dimensions": ["dt.entity.service_method"],
                "dimensionMap": {
                    "dt.entity.service_method": "SERVICE_METHOD-ABC123DEF456",
                    "dt.entity.service_method.name": "processPayment - payment.service.com"
                },
                "timestamps": timestamps.copy(),
                "values": [random.randint(500, 1000) for _ in timestamps]
            }
        ]
    else:
        # Default series for other metric types
        series = [
            {
                "dimensions": [],
                "dimensionMap": {},
                "timestamps": timestamps.copy(),
                "values": [random.uniform(0, 100) for _ in timestamps]
            }
        ]
    
    return series

