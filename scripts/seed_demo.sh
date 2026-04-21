#!/bin/bash
set -e

BASE_URL="http://localhost:8000"

echo "Creating demo service: Payment Gateway..."
SVC=$(curl -sf -X POST "$BASE_URL/services" \
  -H "Content-Type: application/json" \
  -d '{"name": "Payment Gateway", "description": "Main payment processing service"}')
SVC_ID=$(echo "$SVC" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Adding endpoints..."
curl -sf -X POST "$BASE_URL/services/$SVC_ID/endpoints" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://test-service:8001/health"}' > /dev/null

curl -sf -X POST "$BASE_URL/services/$SVC_ID/endpoints" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://test-service:8001/api/v1/data"}' > /dev/null

echo "Adding responsible person..."
curl -sf -X POST "$BASE_URL/services/$SVC_ID/responsible" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ivan Ivanov", "email": "ivanov@company.ru"}' > /dev/null

echo "Setting SLA target: 99.9%..."
curl -sf -X PUT "$BASE_URL/services/$SVC_ID/sla-config" \
  -H "Content-Type: application/json" \
  -d '{"target_percent": 99.9}' > /dev/null

echo "Done. Service ID: $SVC_ID"
echo "Open http://localhost:8000/docs to explore the API"
echo "Open http://localhost:8025 to view emails in MailHog"
