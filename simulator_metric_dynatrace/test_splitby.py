#!/usr/bin/env python3
"""Test script to verify splitBy logic"""

metric_selector = 'builtin:service.keyRequest.count.total:splitBy("dt.entity.service_method")'

# Parse metric selector
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

# Check for splitBy
has_split_by = ':splitBy(' in metric_selector

print(f"Metric selector: {metric_selector}")
print(f"Base metric ID: {base_metric_id}")
print(f"Has splitBy: {has_split_by}")

# Test with the mock data
from mock_data import METRICS, get_mock_multi_series_data
import json

matching_metric = next((m for m in METRICS if m['metricId'] == base_metric_id), None)
print(f"Matching metric: {matching_metric['metricId'] if matching_metric else 'None'}")

if matching_metric and has_split_by:
    series_data = get_mock_multi_series_data(
        matching_metric['metricId'], 
        1000000,
        2000000,
        '5m'
    )
    print(f"\nGenerated {len(series_data)} series:")
    for i, series in enumerate(series_data):
        print(f"  Series {i+1}: {series['dimensionMap']}")
        print(f"    Timestamps: {len(series['timestamps'])} points")
        print(f"    Values: {series['values'][:3]}...")
