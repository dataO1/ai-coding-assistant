#!/usr/bin/env bash

set -euo pipefail

AGENT_URL="${AI_AGENT_SERVER_URL:-http://localhost:3000}"

PIPELINE="${1:-supervisor}"

QUERY="${@:2}"

if [ -z "$QUERY" ]; then
  echo "Usage: agent [pipeline] <query>"
  echo ""
  echo "Available pipelines:"
  curl -X GET "$AGENT_URL/api/pipelines" \
    -H "Content-Type: application/json" 2>&1 | jq -r '.[] | "  \(.name): \(.description)"' || echo "  (unable to connect to agent server at $AGENT_URL)"
  exit 1
fi

RESPONSE=$(curl -X POST "$AGENT_URL/api/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\", \"context\": \"shell\", \"pipeline\": \"$PIPELINE\"}" 2>&1)

echo "$RESPONSE" | jq -r '.response // .error // .' || echo "$RESPONSE"
