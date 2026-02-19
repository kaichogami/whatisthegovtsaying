#!/bin/bash
set -euo pipefail

echo "=== Step 1: Generate digests ==="
python3 scripts/generate_digest.py

echo "=== Step 2: Build static site ==="
npm run build

echo "=== Step 3: Deploy to Cloudflare Pages ==="
npx wrangler pages deploy dist/ --project-name whatisthegovtsaying
