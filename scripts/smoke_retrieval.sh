#!/usr/bin/env bash
set -euo pipefail

# Simple smoke checks for local services.
# Expected local ports:
# - agent-api: 8000
# - travel-knowledge: 8010
# - travel-products: 8020

AGENT_PORT="${AGENT_API_PORT:-8000}"
KNOW_PORT="${KNOWLEDGE_MCP_PORT:-8010}"
PROD_PORT="${PRODUCTS_MCP_PORT:-8020}"

echo "==> Health checks"
curl -fsS "http://127.0.0.1:${AGENT_PORT}/health" | jq .
curl -fsS "http://127.0.0.1:${KNOW_PORT}/health" | jq .
curl -fsS "http://127.0.0.1:${PROD_PORT}/health" | jq .

echo ""
echo "==> MCP smoke (these endpoints depend on your MCP implementation)"
echo "If your MCP server isn't HTTP-based, replace these with the correct transport."

# Example payloads (match your contracts request shapes)
KNOW_PAYLOAD='{
  "x_contract_version": "1.0",
  "request": {
    "user_query": "dicas para evitar filas na Disney",
    "destination": "Orlando",
    "lang": "pt-BR",
    "debug": true
  }
}'

PROD_PAYLOAD='{
  "x_contract_version": "1.0",
  "request": {
    "query_signature": "orlando:filas_disney:pt-BR",
    "destination": "Orlando",
    "market": "BR",
    "lang": "pt-BR",
    "limit": 5,
    "min_confidence": 0.5
  }
}'

echo ""
echo "==> travel-knowledge (example POST /retrieve)"
curl -fsS -X POST "http://127.0.0.1:${KNOW_PORT}/retrieve" \
  -H "content-type: application/json" \
  -d "${KNOW_PAYLOAD}" | jq .

echo ""
echo "==> travel-products (example POST /candidates)"
curl -fsS -X POST "http://127.0.0.1:${PROD_PORT}/candidates" \
  -H "content-type: application/json" \
  -d "${PROD_PAYLOAD}" | jq .

echo ""
echo "✅ Smoke checks completed"
