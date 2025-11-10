#!/bin/bash

# Quick test script for Dynatrace API Simulator
# Usage: ./quick-test.sh

set -e

API_URL="http://localhost:8080"
API_TOKEN="test-token"

echo "=========================================="
echo "Dynatrace API Simulator - Quick Test"
echo "=========================================="
echo ""

# Check if simulator is running
echo "1. Checking if simulator is running..."
if curl -s --fail "$API_URL/health" > /dev/null 2>&1; then
    echo "   ✓ Simulator is running"
else
    echo "   ✗ Simulator is not running"
    echo ""
    echo "   Start it with: docker-compose up -d"
    echo "   Or with: python app.py"
    exit 1
fi

echo ""
echo "2. Testing health endpoint..."
curl -s "$API_URL/health" | python3 -m json.tool
echo ""

echo "3. Testing authentication (should fail)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v2/metrics")
if [ "$HTTP_CODE" = "401" ]; then
    echo "   ✓ Correctly returned 401 Unauthorized"
else
    echo "   ✗ Expected 401, got $HTTP_CODE"
fi

echo ""
echo "4. Testing list metrics with valid token..."
METRICS_COUNT=$(curl -s -H "Authorization: Api-Token $API_TOKEN" "$API_URL/api/v2/metrics" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['metrics']))")
echo "   ✓ Found $METRICS_COUNT metrics"

echo ""
echo "5. Testing get data points..."
FROM=$(date -d '1 hour ago' +%s)000
TO=$(date +%s)000
curl -s -H "Authorization: Api-Token $API_TOKEN" \
    "$API_URL/api/v2/metrics/builtin:host.cpu.usage?from=$FROM&to=$TO&resolution=5m" \
    | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   ✓ Received {len(data['result'][0]['data'][0]['timestamps'])} data points\")"

echo ""
echo "=========================================="
echo "✓ All tests passed!"
echo "=========================================="
echo ""
echo "Simulator is working correctly at $API_URL"
echo "Use token: $API_TOKEN"
