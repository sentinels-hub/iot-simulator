#!/bin/bash
set -euo pipefail

# test-connection.sh — Test MQTT connectivity for Mode A and Mode B
#
# Prerequisites: mosquitto-clients (apt install mosquitto-clients)
#
# Usage: ./scripts/test-connection.sh [mode]
#   mode: "a" (Mosquitto), "b" (TB Direct), or "both" (default)

MODE=${1:-both}
TIMEOUT=10

echo "=== IoT Gateway Simulator — Connection Test ==="
echo ""

test_mode_a() {
    echo "--- Mode A: Mosquitto via Nginx ---"
    HOST="gw-lora-0001.iberdrola-arenales-26.sentinels.pro"
    PORT="443"
    CLIENT_ID="iot-sim-test-$$"

    echo "Connecting to ${HOST}:${PORT} (WebSocket/TLS)..."

    # Use mosquitto_pub with WebSocket support
    if mosquitto_pub \
        --url "wss://${HOST}:${PORT}/mqtt" \
        -i "${CLIENT_ID}" \
        -t "gw-lora-0001/bme680" \
        -m "{\"SerialNumber\":\"TEST\",\"Temperature\":22.5,\"_test\":true}" \
        --will-topic "gw-lora-0001/status" \
        --will-payload "{\"client\":\"${CLIENT_ID}\",\"status\":\"disconnected\"}" \
        -q 1 \
        --quiet 2>/dev/null; then
        echo "✓ Mode A: Successfully published to ${HOST}:${PORT}"
    else
        echo "✗ Mode A: Failed to connect/publish to ${HOST}:${PORT}"
        echo "  This may indicate network/firewall issues or mosquitto-clients not installed."
    fi
    echo ""
}

test_mode_b() {
    echo "--- Mode B: Direct ThingsBoard PE ---"
    HOST="aiot.sentinels.pro"
    PORT="443"

    # Read token from env
    TOKEN="${IBERDROLA_GATEWAY_TOKEN:-}"
    if [ -z "$TOKEN" ]; then
        echo "✗ Mode B: IBERDROLA_GATEWAY_TOKEN not set"
        echo "  Set it with: export IBERDROLA_GATEWAY_TOKEN=your_token"
        return 1
    fi

    echo "Connecting to ${HOST}:${PORT} (TLS)..."

    if mosquitto_pub \
        -h "${HOST}" \
        -p "${PORT}" \
        -u "${TOKEN}" \
        -P "" \
        -t "v1/gateway/telemetry" \
        -m "{\"BME680_SN_TEST\":[{\"ts\":$(date +%s)000,\"values\":{\"temperature\":22.5}}]}" \
        --capath /etc/ssl/certs/ \
        -q 1 \
        --quiet 2>/dev/null; then
        echo "✓ Mode B: Successfully published to ${HOST}:${PORT}"
    else
        echo "✗ Mode B: Failed to connect/publish to ${HOST}:${PORT}"
        echo "  Check your token and network connectivity."
    fi
    echo ""
}

case "$MODE" in
    a) test_mode_a ;;
    b) test_mode_b ;;
    both)
        test_mode_a
        test_mode_b
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: $0 [a|b|both]"
        exit 1
        ;;
esac

echo "=== Done ==="