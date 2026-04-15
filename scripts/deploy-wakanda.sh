#!/bin/bash
set -euo pipefail

# deploy-wakanda.sh — Deploy IoT Gateway Simulator on Wakanda (Proxmox)
#
# Usage: ./scripts/deploy-wakanda.sh

echo "=== IoT Gateway Simulator — Deploy to Wakanda ==="
echo ""

# Build
echo "[1/3] Building containers..."
docker compose build

# Start
echo "[2/3] Starting containers..."
docker compose up -d

# Health check
echo "[3/3] Waiting for backend health..."
MAX_RETRIES=30
RETRY=0
until curl -sf http://localhost:8000/api/health > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "ERROR: Backend health check failed after ${MAX_RETRIES} retries"
        docker compose logs backend
        exit 1
    fi
    echo "  Waiting for backend... ($RETRY/${MAX_RETRIES})"
    sleep 2
done

echo ""
echo "=== Deployment Successful ==="
echo ""
echo "Frontend:  http://localhost:8080"
echo "Backend:   http://localhost:8000"
echo "API Docs:  http://localhost:8000/docs"
echo "Health:    http://localhost:8000/api/health"
echo ""
echo "Logs:      docker compose logs -f"
echo "Stop:      docker compose down"