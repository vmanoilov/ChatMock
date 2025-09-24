#!/bin/bash

# Smoke test script for ChatMock (Qwen)
# Tests basic functionality: health check, non-stream, and stream calls

set -e

HOST=${1:-127.0.0.1}
PORT=${2:-8000}
BASE_URL="http://$HOST:$PORT"

echo "Running smoke tests against $BASE_URL"

# Function to time and check response
check_response() {
    local url=$1
    local expected_status=$2
    local description=$3

    echo -n "$description... "
    start_time=$(date +%s%3N)
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    end_time=$(date +%s%3N)
    latency=$((end_time - start_time))

    if [ "$status" -eq "$expected_status" ]; then
        echo "✓ ($latency ms)"
    else
        echo "✗ (got $status, expected $expected_status)"
        exit 1
    fi
}

# 1. Health check
check_response "$BASE_URL/healthz" 200 "Health check"

# 2. Non-streaming call
echo -n "Non-streaming call... "
start_time=$(date +%s%3N)
response=$(curl -s -X POST "$BASE_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen",
        "messages": [{"role": "user", "content": "Say hello in one short line"}],
        "stream": false,
        "max_tokens": 10
    }')
end_time=$(date +%s%3N)
latency=$((end_time - start_time))

if echo "$response" | jq -e '.choices[0].message.content' >/dev/null 2>&1; then
    content_length=$(echo "$response" | jq -r '.choices[0].message.content | length')
    echo "✓ ($latency ms, content length: $content_length)"
else
    echo "✗ (invalid response format)"
    echo "Response: $response"
    exit 1
fi

# 3. Streaming call
echo -n "Streaming call... "
start_time=$(date +%s%3N)
response=$(curl -s -X POST "$BASE_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen",
        "messages": [{"role": "user", "content": "Count to 3"}],
        "stream": true,
        "max_tokens": 20
    }')
end_time=$(date +%s%3N)
latency=$((end_time - start_time))

# Check if response contains data: lines and ends with [DONE]
if echo "$response" | grep -q "data: " && echo "$response" | tail -1 | grep -q "\[DONE\]"; then
    data_lines=$(echo "$response" | grep "data: " | wc -l)
    echo "✓ ($latency ms, $data_lines data lines)"
else
    echo "✗ (invalid streaming response)"
    echo "Response: $response"
    exit 1
fi

echo "All smoke tests passed! 🎉"