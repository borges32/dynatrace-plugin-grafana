#!/usr/bin/env python3
"""
Test script for Dynatrace API Simulator authentication
"""

import requests
import json
import time

BASE_URL = "http://localhost:8080"
VALID_TOKEN = "test-token"
INVALID_TOKEN = "invalid-token"


def print_test(title):
    """Print test section header"""
    print("\n" + "="*60)
    print(f"TEST: {title}")
    print("="*60)


def print_response(response):
    """Print response details"""
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)


def test_no_auth():
    """Test request without authentication"""
    print_test("Request without Authorization header")
    response = requests.get(f"{BASE_URL}/api/v2/metrics")
    print_response(response)
    assert response.status_code == 401, "Expected 401 Unauthorized"


def test_invalid_format():
    """Test request with invalid auth format"""
    print_test("Request with invalid Authorization format")
    response = requests.get(
        f"{BASE_URL}/api/v2/metrics",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    print_response(response)
    assert response.status_code == 401, "Expected 401 Unauthorized"


def test_invalid_token():
    """Test request with invalid token"""
    print_test("Request with invalid token")
    response = requests.get(
        f"{BASE_URL}/api/v2/metrics",
        headers={"Authorization": f"Api-Token {INVALID_TOKEN}"}
    )
    print_response(response)
    assert response.status_code == 401, "Expected 401 Unauthorized"


def test_valid_token_list_metrics():
    """Test list metrics with valid token"""
    print_test("List metrics with valid token")
    response = requests.get(
        f"{BASE_URL}/api/v2/metrics",
        headers={"Authorization": f"Api-Token {VALID_TOKEN}"}
    )
    print_response(response)
    assert response.status_code == 200, "Expected 200 OK"
    data = response.json()
    assert "metrics" in data, "Expected 'metrics' in response"
    print(f"\nFound {len(data['metrics'])} metrics")


def test_valid_token_get_data_points():
    """Test get data points with valid token"""
    print_test("Get data points with valid token")
    
    # Get timestamps for last hour
    to_ts = int(time.time() * 1000)
    from_ts = to_ts - (3600 * 1000)  # 1 hour ago
    
    response = requests.get(
        f"{BASE_URL}/api/v2/metrics/builtin:host.cpu.usage",
        headers={"Authorization": f"Api-Token {VALID_TOKEN}"},
        params={
            "from": from_ts,
            "to": to_ts,
            "resolution": "5m"
        }
    )
    print_response(response)
    assert response.status_code == 200, "Expected 200 OK"
    data = response.json()
    assert "result" in data, "Expected 'result' in response"
    print(f"\nReceived {len(data['result'])} result(s)")


def test_valid_token_query_post():
    """Test POST query with valid token"""
    print_test("POST query with valid token")
    
    to_ts = int(time.time() * 1000)
    from_ts = to_ts - (3600 * 1000)
    
    response = requests.post(
        f"{BASE_URL}/api/v2/metrics/query",
        headers={
            "Authorization": f"Api-Token {VALID_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "metricSelector": "builtin:host.cpu.usage",
            "from": from_ts,
            "to": to_ts,
            "resolution": "5m"
        }
    )
    print_response(response)
    assert response.status_code == 200, "Expected 200 OK"


def main():
    """Run all tests"""
    print("="*60)
    print("Dynatrace API Simulator - Authentication Tests")
    print("="*60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Valid Token: {VALID_TOKEN}")
    print(f"Invalid Token: {INVALID_TOKEN}")
    
    try:
        # Test authentication failures
        test_no_auth()
        test_invalid_format()
        test_invalid_token()
        
        # Test successful requests
        test_valid_token_list_metrics()
        test_valid_token_get_data_points()
        test_valid_token_query_post()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except requests.exceptions.ConnectionError:
        print(f"\n✗ ERROR: Could not connect to {BASE_URL}")
        print("Make sure the simulator is running: python app.py")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
