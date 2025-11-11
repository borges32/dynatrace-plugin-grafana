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
        elif "request.count" in metric_id:
            value = random.randint(10, 1000)
        elif "crashCount" in metric_id:
            value = random.randint(0, 50)
        elif "disk" in metric_id:
            value = random.uniform(1000000000, 10000000000)
        else:
            value = random.uniform(0, 100)
        
        data_points.append([current_ts, value])
        current_ts += interval
    
    return data_points
