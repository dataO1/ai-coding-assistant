#!/usr/bin/env bash
AGENT_URL="''${AI_AGENT_SERVER_URL:-http://localhost:3000}"
PIPELINE="''${1:-supervisor}"
QUERY="''${@:2}"

if [ -z "$QUERY" ]; then
echo "Usage: ai [pipeline] <query...>"
curl -s "$AGENT_URL/api/pipelines" 2>/dev/null | ${pkgs.jq}/bin/jq -r '.[] | "  \(.name): \(.description)"' || true
exit 1
fi

curl -s -X POST "$AGENT_URL/api/query" \
-H "Content-Type: application/json" \
-d "{\"query\": \"$QUERY\", \"context\": \"shell\", \"pipeline\": \"$PIPELINE\"}" | jq -r '.response // .error'
