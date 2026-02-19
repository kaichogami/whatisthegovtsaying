#!/bin/bash
set -euo pipefail

echo "=== Initial run ==="
/app/scripts/build_and_deploy.sh

echo "=== Entering daily loop (07:00 UTC) ==="
while true; do
    # Calculate seconds until next 07:00 UTC
    now=$(date -u +%s)
    today_07=$(date -u -d "today 07:00" +%s)
    tomorrow_07=$(date -u -d "tomorrow 07:00" +%s)

    if [ "$now" -lt "$today_07" ]; then
        target=$today_07
    else
        target=$tomorrow_07
    fi

    sleep_seconds=$((target - now))
    echo "Sleeping ${sleep_seconds}s until next 07:00 UTC..."
    sleep "$sleep_seconds"

    echo "=== Daily run: $(date -u) ==="
    /app/scripts/build_and_deploy.sh || echo "Build failed, will retry next cycle"
done
