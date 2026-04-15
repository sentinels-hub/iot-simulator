#!/bin/bash
set -euo pipefail

# deploy-wakanda.sh — Deploy IoT Gateway Simulator to Wakanda via SSH
#
# Usage:
#   ./scripts/deploy-wakanda.sh              # Full deploy (build + start + health)
#   ./scripts/deploy-wakanda.sh status        # Check deployment status
#   ./scripts/deploy-wakanda.sh stop          # Stop containers
#   ./scripts/deploy-wakanda.sh logs          # Tail container logs
#   ./scripts/deploy-wakanda.sh restart       # Restart containers
#   ./scripts/deploy-wakanda.sh smoke         # Run E2E smoke test
#
# Requires: SSH access to Wakanda (ssh wakanda or via WAKANDA_SSH env)
# Requires: .env file with IBERDROLA_GATEWAY_TOKEN

# ─── Configuration ─────────────────────────────────────────────────────

REMOTE_HOST="${WAKANDA_SSH:-wakanda}"
REMOTE_USER="$(ssh -G "$REMOTE_HOST" 2>/dev/null | grep '^user ' | awk '{print $2}' || echo 'agentops')"
REMOTE_DIR="/opt/iot-simulator"
REPO_URL="https://github.com/sentinels-hub/iot-simulator.git"
BRANCH="main"
MAX_HEALTH_RETRIES=30
HEALTH_INTERVAL=2

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

ssh_cmd() {
    ssh -o ConnectTimeout=10 "$REMOTE_HOST" "$@"
}

scp_to() {
    scp -o ConnectTimeout=10 "$1" "$REMOTE_HOST:$2"
}

# ─── Pre-flight ─────────────────────────────────────────────────────────

preflight() {
    info "Checking SSH connectivity to $REMOTE_HOST..."
    if ! ssh_cmd "echo ok" >/dev/null 2>&1; then
        fail "Cannot SSH to $REMOTE_HOST. Check your SSH config."
    fi
    ok "SSH connected"

    info "Checking Docker on remote..."
    if ! ssh_cmd "docker --version" >/dev/null 2>&1; then
        fail "Docker not installed on remote host."
    fi
    if ! ssh_cmd "docker compose version" >/dev/null 2>&1; then
        fail "Docker Compose not installed on remote host."
    fi
    ok "Docker + Compose available"
}

# ─── Deploy ─────────────────────────────────────────────────────────────

deploy() {
    preflight

    # 1. Clone or update repo
    info "Syncing repository to $REMOTE_DIR..."
    ssh_cmd "if [ -d '$REMOTE_DIR/.git' ]; then
        cd $REMOTE_DIR && git fetch origin && git reset --hard origin/$BRANCH
    else
        sudo rm -rf $REMOTE_DIR
        git clone -b $BRANCH $REPO_URL $REMOTE_DIR
    fi"
    ok "Repository synced"

    # 2. Ensure .env exists
    info "Checking .env configuration..."
    if ! ssh_cmd "test -f $REMOTE_DIR/.env"; then
        if [ -f ".env" ]; then
            info "Uploading local .env..."
            scp_to ".env" "$REMOTE_DIR/.env"
        else
            warn "No .env found. Creating from .env.example (you MUST set IBERDROLA_GATEWAY_TOKEN)"
            ssh_cmd "cp $REMOTE_DIR/.env.example $REMOTE_DIR/.env"
        fi
    fi
    ok ".env ready"

    # 3. Build containers
    info "Building Docker containers..."
    ssh_cmd "cd $REMOTE_DIR && docker compose build --quiet" 2>&1 || \
    ssh_cmd "cd $REMOTE_DIR && docker compose build"
    ok "Containers built"

    # 4. Start containers
    info "Starting containers..."
    ssh_cmd "cd $REMOTE_DIR && docker compose down --remove-orphans 2>/dev/null; docker compose up -d"
    ok "Containers started"

    # 5. Health check
    info "Waiting for backend health..."
    RETRY=0
    until ssh_cmd "curl -sf http://localhost:8000/api/health" >/dev/null 2>&1; do
        RETRY=$((RETRY + 1))
        if [ $RETRY -ge $MAX_HEALTH_RETRIES ]; then
            fail "Backend health check failed after ${MAX_HEALTH_RETRIES} retries"
            ssh_cmd "cd $REMOTE_DIR && docker compose logs backend --tail=30"
        fi
        echo "  Waiting... ($RETRY/${MAX_HEALTH_RETRIES})"
        sleep $HEALTH_INTERVAL
    done
    ok "Backend healthy"

    # 6. Verify frontend
    info "Checking frontend..."
    if ssh_cmd "curl -sf -o /dev/null http://localhost:8080" 2>/dev/null; then
        ok "Frontend serving on port 8080"
    else
        warn "Frontend not responding on port 8080 yet (may need a moment)"
    fi

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Deployment Successful!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Frontend:  http://iot-sim.sentinels.pro"
    echo "  Backend:   http://iot-sim.sentinels.pro/api/health"
    echo "  API Docs:  http://iot-sim.sentinels.pro/docs"
    echo "  Remote:    ssh $REMOTE_HOST"
    echo "  Logs:      $0 logs"
    echo ""
}

# ─── Status ─────────────────────────────────────────────────────────────

status() {
    info "Checking deployment status on $REMOTE_HOST..."
    echo ""
    ssh_cmd "cd $REMOTE_DIR 2>/dev/null && {
        echo '=== Containers ==='
        docker compose ps -a 2>/dev/null
        echo ''
        echo '=== Health ==='
        curl -sf http://localhost:8000/api/health 2>/dev/null || echo 'Backend not responding'
        echo ''
        echo '=== Frontend ==='
        curl -sf -o /dev/null -w 'HTTP %{http_code}' http://localhost:8080 2>/dev/null || echo 'Frontend not responding'
        echo ''
        echo '=== Disk ==='
        df -h / | tail -1
    } || echo 'Repository not deployed at $REMOTE_DIR'"
}

# ─── Stop ───────────────────────────────────────────────────────────────

stop() {
    info "Stopping containers on $REMOTE_HOST..."
    ssh_cmd "cd $REMOTE_DIR && docker compose down"
    ok "Containers stopped"
}

# ─── Logs ───────────────────────────────────────────────────────────────

logs() {
    ssh_cmd "cd $REMOTE_DIR && docker compose logs -f --tail=50 ${1:-}"
}

# ─── Restart ────────────────────────────────────────────────────────────

restart() {
    info "Restarting containers on $REMOTE_HOST..."
    ssh_cmd "cd $REMOTE_DIR && docker compose restart"
    ok "Containers restarted"
}

# ─── Smoke test ─────────────────────────────────────────────────────────

smoke() {
    info "Running E2E smoke test against $REMOTE_HOST..."

    local BASE="http://localhost:8000"

    echo ""
    echo -e "${BLUE}1. Health check${NC}"
    local health
    health=$(ssh_cmd "curl -sf $BASE/api/health")
    if echo "$health" | grep -q '"status":"ok"'; then
        ok "Backend healthy: $health"
    else
        fail "Backend unhealthy: $health"
    fi

    echo ""
    echo -e "${BLUE}2. List profiles${NC}"
    local profiles
    profiles=$(ssh_cmd "curl -sf $BASE/api/profiles")
    local pcount
    pcount=$(echo "$profiles" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('profiles',[])))" 2>/dev/null || echo "?")
    ok "Found $pcount profiles"

    echo ""
    echo -e "${BLUE}3. Create simulation (example-gateway)${NC}"
    local sim
    sim=$(ssh_cmd "curl -sf -XPOST '$BASE/api/simulations?profile=example-gateway'")
    local sim_id
    sim_id=$(echo "$sim" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
    if [ -n "$sim_id" ]; then
        ok "Simulation created: id=$sim_id"
    else
        fail "Failed to create simulation: $sim"
    fi

    echo ""
    echo -e "${BLUE}4. List simulations${NC}"
    local sims
    sims=$(ssh_cmd "curl -sf $BASE/api/simulations")
    local scount
    scount=$(echo "$sims" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
    ok "Found $scount simulation(s)"

    echo ""
    echo -e "${BLUE}5. Get simulation detail${NC}"
    local detail
    detail=$(ssh_cmd "curl -sf $BASE/api/simulations/$sim_id")
    local sim_status
    sim_status=$(echo "$detail" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "?")
    ok "Simulation status: $sim_status"

    echo ""
    echo -e "${BLUE}6. Delete simulation${NC}"
    ssh_cmd "curl -sf -XDELETE $BASE/api/simulations/$sim_id -o /dev/null -w '%{http_code}'" | grep -q "204" && \
        ok "Simulation deleted" || warn "Delete returned non-204"

    echo ""
    echo -e "${BLUE}7. Frontend check${NC}"
    local fstatus
    fstatus=$(ssh_cmd "curl -sf -o /dev/null -w '%{http_code}' http://localhost:8080")
    ok "Frontend HTTP $fstatus"

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
    logs)    preflight && logs "${2:-}" ;;
    restart) preflight && restart ;;
    smoke)   preflight && smoke  ;;
    *)
        echo "Usage: $0 {deploy|status|stop|logs|restart|smoke}"
        echo ""
        echo "  deploy   — Full deploy: clone/build/start/health (default)"
        echo "  status   — Check deployment status"
        echo "  stop     — Stop containers"
        echo "  logs     — Tail container logs (optional: service name)"
        echo "  restart  — Restart containers"
        echo "  smoke    — Run E2E smoke test"
        exit 1
        ;;
esac
