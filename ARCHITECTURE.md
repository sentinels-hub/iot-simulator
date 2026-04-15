# Architecture — IoT Gateway Simulator

## Overview

The IoT Gateway Simulator replaces a non-functional physical field gateway by sending realistic BSEC telemetry from simulated Wingman devices to ThingsBoard PE. It runs on **Wakanda** (a Proxmox VM with an external IP), simulating traffic that originates from outside the network — exactly like a real gateway in the field.

## Architecture Context — Sentinels IoT Pipeline

```
CAMPO (Wingman, sensores LoRa/wired)
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│  Gateway Físico en el monte                               │
│  Panel solar, DNS → IP pública → Router → Puerto 443     │
│  ej: gw-lora-0001.iberdrola-arenales-26.sentinels.pro    │
└──────┬──────────────────────────────────┬────────────────┘
       │ SI viene por LoRa               │ SI NO viene por LoRa
       ▼                                 │
┌──────────────┐                         │
│  ChirpStack   │                         │
│  GW-LORA      │  ◄── 1 per company     │
│  Multi-tenant │     1 tenant per project│
└──────┬───────┘                         │
       │                                 │
       ▼                                 ▼
┌──────────────────────────────────────────────────────────┐
│  ThingsBoard IoT Gateway  ◄── ALWAYS, 1 VM per tenant   │
│  (VM203, gw-iot-direct-ingest)                           │
│  Subscribed to Mosquitto + connected to TB PE             │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│  ThingsBoard PE (aiot.sentinels.pro)                     │
│  └── Tenant: "Iberdrola Arenales 2026"                  │
│      ├── Gateway device (auto-creates child devices)     │
│      └── Dashboards, alerts, rules                       │
└──────────────────────────────────────────────────────────┘
```

### Key Rules

1. **TB IoT Gateway is ALWAYS present** — every tenant in TB PE has its own VM with a ThingsBoard IoT Gateway.
2. **ChirpStack (GW-LORA) is optional** — only for LoRa devices. Not all data flows through it.
3. **ChirpStack is multi-tenant** — 1 company-wide installation, but 1 ChirpStack tenant per TB PE tenant.

## Simulator Connection Modes

### Mode A — Via Mosquitto + Nginx (Primary, realistic)

```
Simulator (Wakanda)
  → MQTT/WebSocket/TLS to gw-lora-XXXX.iberdrola-arenales-26.sentinels.pro:443
  → Nginx (SNI routing by hostname)
  → Mosquitto (10.0.60.43:9001 internal)
  → TB Gateway subscribed to gw-lora-0001/#
  → Converts JSON → v1/gateway/telemetry
  → ThingsBoard PE (Tenant: "Iberdrola Arenales 2026")
```

**MQTT Connection details:**
- Host: `gw-lora-XXXX.iberdrola-arenales-26.sentinels.pro`
- Port: 443
- Protocol: MQTT over WebSocket over TLS
- Path: `/mqtt`
- Auth: Anonymous (ClientID only, no username/password)
- ClientID pattern: `gw-simulator-001` (unique per simulation)
- Publish topic: `gw-lora-0001/bme680` (configurable per profile)

**Mosquitto auth:** Anonymous, no credentials. Access control is by topic ACLs, not by login.

### Mode B — Direct to TB PE (Secondary, for testing/debugging)

```
Simulator (Wakanda)
  → MQTT/TLS to aiot.sentinels.pro:443
  → Auth: Access Token as MQTT username (G1P8QqXj15Vmzu7SHdxd)
  → Publish to: v1/gateway/telemetry
  → ThingsBoard PE creates child devices dynamically
```

**MQTT Connection details:**
- Host: `aiot.sentinels.pro`
- Port: 443
- Protocol: MQTT over TLS (no WebSocket needed)
- Auth: Access token as MQTT username, empty password
- Token: stored in env var `IBERDROLA_GATEWAY_TOKEN`
- Publish topic: `v1/gateway/telemetry`

**Gateway telemetry payload format:**
```json
{
  "gw-iot-direct-ingest": [
    {
      "ts": 1713177600000,
      "values": {
        "temperature": 33.15,
        "pressure": 976.03,
        "humidity": 22.91,
        "gasResistance": 96786.39,
        "gasIndex": 0
      }
    }
  ],
  "BME680_SN_001": [
    {
      "ts": 1713177600000,
      "values": {
        "temperature": 33.15,
        "pressure": 976.03,
        "humidity": 22.91,
        "gasResistance": 96786.39,
        "gasIndex": 0
      }
    }
  ]
}
```

## DNS Configuration — Configured Gateways

| Gateway ID | Hostname | IP | Protocol | Port |
|---|---|---|---|---|
| gw-lora-0001 | gw-lora-0001.iberdrola-arenales-26.sentinels.pro | 2.136.46.136 | MQTT/WebSocket + TLS | 443 |
| gw-lora-0002 | gw-lora-0002.iberdrola-arenales-26.sentinels.pro | 2.136.46.136 | MQTT/WebSocket + TLS | 443 |
| gw-lora-0003 | gw-lora-0003.iberdrola-arenales-26.sentinels.pro | 2.136.46.136 | MQTT/WebSocket + TLS | 443 |
| gw-lora-0004 | gw-lora-0004.iberdrola-arenales-26.sentinels.pro | 2.136.46.136 | MQTT/WebSocket + TLS | 443 |
| gw-lora-0005 | gw-lora-0005.iberdrola-arenales-26.sentinels.pro | 2.136.46.136 | MQTT/WebSocket + TLS | 443 |

All resolve to the same public IP. Nginx routes by SNI (hostname).

## BSEC Telemetry — Wingman Device Data

Raw BSEC output from a Wingman sensor:

```
SerialNumber: 00000000002C
BSEC outputs:
  Time stamp = 7164111
  Temperature = 33.15
  Pressure    = 976.03
  Humidity    = 22.91
  Gas resist. = 96786.39
  Gas index   = 0
  Voltaje bateria: 4.17
  model: Nordic
  Perfil: ULP
  Ciclo: 222
```

### Simulated telemetry keys

| Key | Unit | Realistic Range | Drift/tick | Notes |
|---|---|---|---|---|
| temperature | °C | 15.0 – 50.0 | ±0.5 | Ambient temperature |
| pressure | hPa | 950.0 – 1050.0 | ±1.0 | Atmospheric pressure |
| humidity | %RH | 10.0 – 95.0 | ±2.0 | Relative humidity |
| gasResistance | Ω | 1000 – 15000000 | variable | Raw gas sensor resistance |
| gasIndex | IAQ | 0 – 500 | ±5 | BSEC air quality index |
| batteryVoltage | V | 3.0 – 4.2 | ±0.01 | Battery voltage |
| model | string | "Nordic" | — | Device model (static) |
| perfil | string | "ULP" | — | Power profile (static) |
| ciclo | int | 1 – 100000 | +1 | Transmission cycle counter |

### Device naming

- SerialNumber/DevEUI: `0000000000XXXX` (12-char hex)
- ThingsBoard device name: `BME680_SN_001` pattern
- ClientID for Mosquitto: `gw-simulator-001`

## Tenant Architecture — Iberdrola Arenales 2026

```
ThingsBoard PE (aiot.sentinels.pro)
├── Tenant: "Iberdrola Arenales 2026"
│   ├── Gateway: gw-iot-direct-ingest
│   │   ├── Token: G1P8QqXj15Vmzu7SHdxd (env: IBERDROLA_GATEWAY_TOKEN)
│   │   └── Child devices created dynamically on first telemetry
│   │       ├── BME680_SN_001 (type: BME680 Sensor)
│   │       ├── BME680_SN_002 (type: BME680 Sensor)
│   │       └── ...
│   └── User Accounts:
│       ├── admin@iberdrola-arenales-26 (tenant admin)
│       └── operator@iberdrola-arenales-26 (dashboard viewer)
└── Tenant: "Sentinels Demo" (isolated, different tokens)
```

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Backend | Python + FastAPI | API + simulation engine |
| Frontend | React + Vite | Monitoring dashboard |
| MQTT Client | paho-mqtt | Telemetry transport (both modes) |
| Container | Docker Compose | Deployment on Wakanda |
| Persistence | SQLite + JSON | Simulation logs and state |

## Deployment — Wakanda (Proxmox)

- Wakanda is **outside** the network where TB Gateway and TB PE reside
- This is intentional: simulates real external gateway traffic
- Persistent volumes for config and logs

### Domain and Access

| Service | URL | Port |
|---|---|---|
| Frontend (UI) | https://iot-sim.sentinels.pro | 443 |
| Backend API | https://iot-sim.sentinels.pro/api | 443 |
| Backend API docs | https://iot-sim.sentinels.pro/docs | 443 |

- Nginx reverse proxy on Wakanda terminates TLS for `iot-sim.sentinels.pro`
- Frontend and backend are served through the same domain
- Let's Encrypt certificate for the domain
- Backend runs on port 8000 internally, proxied to /api
- Frontend runs on port 80 internally, proxied to /

### DNS Configuration

```
iot-sim.sentinels.pro.  300  IN  A  <WAKANDA_PUBLIC_IP>
```

### Nginx Configuration (Wakanda)

```nginx
server {
    listen 443 ssl http2;
    server_name iot-sim.sentinels.pro;

    ssl_certificate /etc/letsencrypt/live/iot-sim.sentinels.pro/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/iot-sim.sentinels.pro/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-Ip $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-Ip $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Backend API docs
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }

    # WebSocket for live logs
    location /api/simulations/ {
        proxy_pass http://127.0.0.1:8000/api/simulations/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```