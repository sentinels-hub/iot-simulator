# IoT Gateway Simulator

Simulates a field gateway transmitting telemetry data to ThingsBoard PE via MQTT (and optionally HTTP). Designed to replace a non-functional physical gateway during testing and validation.

## Features

- **Configurable device profiles** — define N devices with sensor types, intervals, and data ranges
- **MQTT transport** — sends telemetry to ThingsBoard using standard `v1/devices/me/telemetry` topic
- **HTTP transport** — optional REST endpoint for telemetry push
- **Cron-style scheduling** — run for a fixed duration or indefinitely until stopped
- **Real-time monitoring UI** — minimal React dashboard to start/stop/monitor simulations
- **Docker Compose** — single-command deployment on Wakanda (Proxmox)

## Quick Start

```bash
# Clone
git clone https://github.com/sentinels-hub/iot-simulator.git
cd iot-simulator

# Configure
cp profiles/example-gateway.yaml profiles/local/my-gateway.yaml
# Edit profile with your ThingsBoard host, device tokens, etc.

# Run
docker compose up -d

# Access
# Frontend: http://localhost:8080
# Backend API: http://localhost:8000/docs
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (React)                │
│         Config · Start/Stop · Monitor            │
└──────────────────┬──────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────┐
│               Backend (FastAPI)                   │
│    Simulator Engine · Device Factory · Scheduler  │
└──────┬───────────────────────────────┬───────────┘
       │ MQTT                          │ HTTP
┌──────▼──────────┐         ┌─────────▼──────────┐
│  Mosquitto       │         │  ThingsBoard PE    │
│  (optional)      │         │  (Wakanda)         │
└─────────────────┘         └────────────────────┘
```

## Profile Configuration

See `profiles/example-gateway.yaml` for a complete example.

```yaml
name: "field-gateway-sim"
target:
  host: "aiot.sentinels.pro"
  port: 1883
  protocol: "mqtt"
  topic: "v1/devices/me/telemetry"

devices:
  count: 50
  prefix: "wingman-sim"
  token_pattern: "DEVICE_TOKEN_{index}"

telemetry:
  interval_seconds: 30
  keys:
    - temperature
    - humidity
    - pressure
    - co2
    - battery

schedule:
  mode: "duration"  # "duration" or "infinite"
  duration_minutes: 60
```

## Deployment on Wakanda

```bash
docker compose -f docker-compose.yml up -d
```

Exposes frontend on port 8080, backend API on port 8000.

## License

Private — Sentinels Hub