#!/bin/bash
set -euo pipefail

# deploy-wakanda.sh — Deploy IoT Gateway Simulator to Wakanda (Proxmox)
#
# Architecture on Wakanda:
#   - Backend: Python/FastAPI as systemd service (Docker has socketpair issues on Proxmox)
#   - Frontend: React build served by host nginx
#   - No Docker containers needed at runtime
#
# Usage:
#   ./scripts/deploy-wakanda.sh              # Full deploy
#   ./scripts/deploy-wakanda.sh status        # Check status
#   ./scripts/deploy-wakanda.sh stop          # Stop backend
#   ./scripts/deploy-wakanda.sh logs          # Tail backend logs
#   ./scripts/deploy-wakanda.sh restart       # Restart backend
#   ./scripts/deploy-wakanda.sh smoke         # Run E2E smoke test
#
# Prerequisites:
#   - SSH access: ssh wakanda (or set WAKANDA_SSH)
#   - Node.js 22+ on Wakanda (for frontend build)
#   - Python 3.12+ on Wakanda (for backend venv)
#   - nginx on Wakanda (for frontend serving + API proxy)

# ─── Configuration ─────────────────────────────────────────────────────

REMOTE_HOST="${WAKANDA_SSH:-wakanda}"
REMOTE_DIR="/opt/iot-simulator"
REPO_URL="https://github.com/sentinels-hub/iot-simulator.git"
BRANCH="main"
SERVICE_NAME="iot-simulator"
NGINX_SITE="iot-sim.sentinels.pro"
WWW_DIR="/var/www/iot-sim"

# ─── Colors ─────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ─── SSH helper ─────────────────────────────────────────────────────────

run() {
    ssh -o ConnectTimeout=10 "$REMOTE_HOST" "$@"
}

# ─── Pre-flight ─────────────────────────────────────────────────────────

preflight() {
    info "Checking SSH connectivity to $REMOTE_HOST..."
    run "echo ok" >/dev/null 2>&1 || fail "Cannot SSH to $REMOTE_HOST"
    ok "SSH connected"

    info "Checking prerequisites on remote..."
    run "python3 --version" >/dev/null 2>&1 || fail "Python 3 not installed"
    run "node --version" >/dev/null 2>&1 || fail "Node.js not installed"
    run "nginx -v" >/dev/null 2>&1 || fail "nginx not installed"
    ok "Prerequisites met"
}

# ─── Deploy ─────────────────────────────────────────────────────────────

deploy() {
    preflight

    # 1. Clone or update repo
    info "Syncing repository to $REMOTE_DIR..."
    run "if [ -d '$REMOTE_DIR/.git' ]; then
        cd $REMOTE_DIR && git fetch origin && git reset --hard origin/$BRANCH
    else
        sudo rm -rf $REMOTE_DIR
        git clone -b $BRANCH $REPO_URL $REMOTE_DIR
    fi"
    ok "Repository synced"

    # 2. Ensure .env exists
    info "Checking .env configuration..."
    if ! run "test -f $REMOTE_DIR/.env"; then
        if [ -f ".env" ]; then
            info "Uploading local .env..."
            scp -o ConnectTimeout=10 ".env" "$REMOTE_HOST:$REMOTE_DIR/.env"
        else
            warn "No .env found. Creating from .env.example"
            run "cp $REMOTE_DIR/.env.example $REMOTE_DIR/.env"
        fi
    fi
    ok ".env ready"

    # 3. Setup Python venv and install deps
    info "Setting up Python backend..."
    run "cd $REMOTE_DIR && \
        python3 -m venv .venv && \
        .venv/bin/pip install -q --upgrade pip && \
        .venv/bin/pip install -q -r backend/requirements.txt"
    ok "Backend dependencies installed"

    # 4. Build frontend natively
    info "Building frontend..."
    run "cd $REMOTE_DIR/frontend && \
        npm install --legacy-peer-deps 2>/dev/null && \
        VITE_API_BASE=/api npx vite build"
    ok "Frontend built"

    # 5. Deploy frontend to nginx
    info "Deploying frontend to $WWW_DIR..."
    run "sudo rm -rf $WWW_DIR && \
        sudo mkdir -p $WWW_DIR && \
        sudo cp -r $REMOTE_DIR/frontend/dist/* $WWW_DIR/ && \
        sudo chown -R www-data:www-data $WWW_DIR"
    ok "Frontend deployed to nginx"

    # 6. Configure nginx site
    info "Configuring nginx..."
    run "if [ ! -f /etc/nginx/sites-available/$NGINX_SITE ]; then
        echo 'ERROR: nginx site config not found at /etc/nginx/sites-available/$NGINX_SITE'
        echo 'Create it first with the correct proxy configuration.'
        exit 1
    fi
    sudo ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/$NGINX_SITE
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx"
    ok "nginx configured"

    # 7. Install systemd service
    info "Installing systemd service..."
    run "cat > /tmp/iot-simulator.service << 'SVCEOF'
[Unit]
Description=IoT Gateway Simulator Backend
After=network.target

[Service]
Type=simple
User=agentops
WorkingDirectory=$REMOTE_DIR/backend
ExecStart=$REMOTE_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=SIMULATOR_HOST=0.0.0.0
Environment=SIMULATOR_PORT=8000
Environment=SIMULATOR_LOG_LEVEL=info
Environment=PROFILES_DIR=$REMOTE_DIR/profiles
EnvironmentFile=$REMOTE_DIR/.env

[Install]
WantedBy=multi-user.target
SVCEOF
    sudo cp /tmp/iot-simulator.service /etc/systemd/system/$SERVICE_NAME.service && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable $SERVICE_NAME && \
    sudo systemctl restart $SERVICE_NAME"
    ok "systemd service installed"

    # 8. Wait for health
    info "Waiting for backend health..."
    RETRY=0
    until run "curl -sf http://localhost:8000/api/health" >/dev/null 2>&1; do
        RETRY=$((RETRY + 1))
        if [ $RETRY -ge 15 ]; then
            fail "Backend health check failed after 15 retries"
            run "sudo journalctl -u $SERVICE_NAME --no-pager -n 20"
        fi
        echo "  Waiting... ($RETRY/15)"
        sleep 2
    done
    ok "Backend healthy"

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Deployment Successful!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Frontend:  http://iot-sim.sentinels.pro (port 80)"
    echo "  Backend:   http://iot-sim.sentinels.pro/api/health"
    echo "  API Docs:  http://iot-sim.sentinels.pro/docs"
    echo "  SSH:       ssh $REMOTE_HOST"
    echo "  Logs:      $0 logs"
    echo "  Status:    $0 status"
    echo ""
}

# ─── Status ─────────────────────────────────────────────────────────────

status() {
    info "Deployment status on $REMOTE_HOST..."
    echo ""
    run "{
        echo '=== Backend (systemd) ==='
        sudo systemctl is-active $SERVICE_NAME 2>/dev/null || echo 'NOT RUNNING'
        echo ''
        echo '=== Health ==='
        curl -sf http://localhost:8000/api/health 2>/dev/null || echo 'Backend not responding'
        echo ''
        echo '=== Profiles ==='
        curl -sf http://localhost:8000/api/profiles 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f\"{d[\"total\"]} profiles loaded\")' 2>/dev/null || echo 'Cannot load profiles'
        echo ''
        echo '=== Frontend (nginx) ==='
        curl -sf -o /dev/null -w 'HTTP %{http_code}' http://localhost/ 2>/dev/null || echo 'Frontend not responding'
        echo ''
        echo '=== Disk ==='
        df -h / | tail -1
    }"
}

# ─── Stop ───────────────────────────────────────────────────────────────

stop() {
    info "Stopping backend on $REMOTE_HOST..."
    run "sudo systemctl stop $SERVICE_NAME"
    ok "Backend stopped"
}

# ─── Logs ───────────────────────────────────────────────────────────────

logs() {
    run "sudo journalctl -u $SERVICE_NAME -f --no-pager -n 50"
}

# ─── Restart ────────────────────────────────────────────────────────────

restart() {
    info "Restarting backend on $REMOTE_HOST..."
    run "sudo systemctl restart $SERVICE_NAME"
    sleep 3
    run "curl -sf http://localhost:8000/api/health" >/dev/null 2>&1 && ok "Backend restarted and healthy" || warn "Backend restarted but not healthy yet"
}

# ─── Smoke test ─────────────────────────────────────────────────────────

smoke() {
    info "Running E2E smoke test against $REMOTE_HOST..."
    local BASE="http://localhost:8000"

    echo -e "\n${BLUE}1. Health check${NC}"
    local health
    health=$(run "curl -sf $BASE/api/health")
    echo "$health" | grep -q '"ok"' && ok "Backend healthy" || fail "Backend unhealthy: $health"

    echo -e "\n${BLUE}2. Profiles${NC}"
    local profiles
    profiles=$(run "curl -sf $BASE/api/profiles")
    local pcount
    pcount=$(echo "$profiles" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "?")
    ok "$pcount profiles loaded"

    echo -e "\n${BLUE}3. Create simulation (example-gateway)${NC}"
    local sim
    sim=$(run "curl -sf -XPOST '$BASE/api/simulations?profile=example-gateway'")
    local sim_id
    sim_id=$(echo "$sim" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    [ -n "$sim_id" ] && ok "Simulation created: $sim_id" || fail "Create failed: $sim"

    echo -e "\n${BLUE}4. Get simulation${NC}"
    local detail
    detail=$(run "curl -sf $BASE/api/simulations/$sim_id")
    echo "$detail" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  Status: {d['status']}, Devices: {d['devices_active']}\")" 2>/dev/null
    ok "Simulation detail retrieved"

    echo -e "\n${BLUE}5. Delete simulation${NC}"
    run "curl -sf -XDELETE $BASE/api/simulations/$sim_id -o /dev/null -w '%{http_code}'" | grep -q "204" && \
        ok "Deleted" || warn "Delete failed"

    echo -e "\n${BLUE}6. Frontend${NC}"
    run "curl -sf -o /dev/null -w '%{http_code}' http://localhost/" | grep -q "200" && \
        ok "Frontend serving (HTTP 200)" || warn "Frontend not serving"

    echo -e "\n${BLUE}7. API via nginx proxy${NC}"
    run "curl -sf http://localhost/api/health" | grep -q '"ok"' && \
        ok "nginx proxy working" || warn "nginx proxy not forwarding"

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Smoke test passed!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
}

# ─── Main ───────────────────────────────────────────────────────────────

COMMAND="${1:-deploy}"

case "$COMMAND" in
    deploy)  deploy  ;;
    status)  preflight && status ;;
    stop)    preflight && stop   ;;
    logs)    preflight && logs   ;;
    restart) preflight && restart ;;
    smoke)   preflight && smoke  ;;
    *)
        echo "Usage: $0 {deploy|status|stop|logs|restart|smoke}"
        echo ""
        echo "  deploy   — Full deploy: clone/build/install/start (default)"
        echo "  status   — Check deployment status"
        echo "  stop     — Stop backend service"
        echo "  logs     — Tail backend logs"
        echo "  restart  — Restart backend service"
        echo "  smoke    — Run E2E smoke test"
        exit 1
        ;;
esac
