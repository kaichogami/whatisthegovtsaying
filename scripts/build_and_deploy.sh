#!/bin/bash
set -euo pipefail

echo "=== Step 1: Generate digests ==="
python3 scripts/generate_digest.py

echo "=== Step 2: Build static site ==="
npm run build

echo "=== Step 3: Deploy to Sutrena ==="
cd dist && zip -r ../site.zip . && cd ..
SIZE=$(stat -c%s site.zip)

# Phase 1: Presign
PRESIGN=$(curl -sf -X POST "$SUTRENA_URL/api/deploy" \
  -H "Authorization: Bearer $SUTRENA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"sizeBytes\": $SIZE}")
DEPLOY_ID=$(echo "$PRESIGN" | jq -r '.deployId')
UPLOAD_URL=$(echo "$PRESIGN" | jq -r '.uploadUrl')

# Upload zip
curl -sf -X PUT "$UPLOAD_URL" --data-binary "@site.zip" -H "Content-Type: application/zip"

# Phase 2: Process
curl -sf -X POST "$SUTRENA_URL/api/deploy/$DEPLOY_ID/process" \
  -H "Authorization: Bearer $SUTRENA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"subdomainId\": \"$SUTRENA_SUBDOMAIN_ID\"}"

rm -f site.zip
echo "=== Deploy complete ==="
