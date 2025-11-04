#!/usr/bin/env bash

set -euo pipefail

AGENT_URL="${AI_AGENT_SERVER_URL:-http://localhost:3000}"

QUERY="${*:1}"

if [ -z "$QUERY" ]; then
  echo "Usage: agent <query>"
  echo ""
  echo "Available pipelines:"
  RESPONSE=$(curl -s -X GET "$AGENT_URL/api/pipelines" \
    -H "Content-Type: application/json" 2>&1) || true

  # Debug: show raw response
  # if echo "$RESPONSE" | grep -q "^{"; then
  #   echo "$RESPONSE" | jq -r '.[] | "  \(.name): \(.description)"' 2>/dev/null || echo "  (jq parse failed)"
  # else
  #   echo "  Raw response: $RESPONSE"
  #   echo "  (Server at $AGENT_URL is not responding with JSON)"
  # fi
  # exit 1
fi

RESPONSE=$(curl -s -X POST "$AGENT_URL/api/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\", \"context\": \"shell\", \"working_dir\": \"$(pwd)\"}" 2>&1) || true

if echo "$RESPONSE" | grep -q "^{"; then
  echo "$RESPONSE" | jq -r '.response // .error // .'
else
  echo "Error: $RESPONSE"
fi
