"""Connectivity check endpoint — test MQTT connectivity to target hosts."""

import logging
import ssl
import time
from typing import Optional

import paho.mqtt.client as mqtt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models import (
    MqttProtocol,
    MosquittoViaNginxConfig,
    TbDirectConfig,
    TransportMode,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectivity", tags=["connectivity"])


class ConnectivityCheckRequest(BaseModel):
    """Request body for connectivity check."""

    mode: TransportMode = Field(default=TransportMode.MOSQUITTO_VIA_NGINX)
    mosquitto: Optional[MosquittoViaNginxConfig] = None
    tb_direct: Optional[TbDirectConfig] = None


class ConnectivityResult(BaseModel):
    """Result of a connectivity check."""

    mode: str
    host: str
    port: int
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@router.post("/check", response_model=ConnectivityResult)
async def check_connectivity(body: ConnectivityCheckRequest):
    """Test MQTT connectivity to a target host.

    Attempts a brief MQTT connection to verify reachability and measure latency.
    """
    if body.mode == TransportMode.MOSQUITTO_VIA_NGINX:
        config = body.mosquitto or MosquittoViaNginxConfig()
        return _check_mosquitto(config)
    elif body.mode == TransportMode.TB_DIRECT:
        config = body.tb_direct or TbDirectConfig()
        return _check_tb_direct(config)
    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown transport mode: {body.mode}"
        )


def _check_mosquitto(config: MosquittoViaNginxConfig) -> ConnectivityResult:
    """Test Mode A connectivity — Mosquitto via Nginx."""
    connected = False
    error_msg = None
    start = time.monotonic()

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal connected
        if reason_code == 0:
            connected = True

    def on_disconnect(client, userdata, flags, reason_code, properties):
        pass

    client = None
    try:
        if config.mqtt_protocol == MqttProtocol.WEBSOCKETS:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"iot-sim-check-{int(time.time())}",
                transport="websockets",
            )
            client.ws_set_options(path=config.mqtt_websocket_path)
        else:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"iot-sim-check-{int(time.time())}",
                transport="tcp",
            )

        if config.mqtt_use_tls:
            client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            client.tls_insecure_set(False)

        if config.mqtt_username:
            client.username_pw_set(config.mqtt_username, config.mqtt_password)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        client.connect(config.mqtt_host, config.mqtt_port, keepalive=5)
        client.loop_start()

        # Wait up to 5 seconds for connection
        for _ in range(50):
            if connected:
                break
            time.sleep(0.1)

        latency = round((time.monotonic() - start) * 1000, 1)

    except Exception as e:
        error_msg = str(e)
        latency = round((time.monotonic() - start) * 1000, 1)
    finally:
        if client:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass

    return ConnectivityResult(
        mode="mosquitto_via_nginx",
        host=config.mqtt_host,
        port=config.mqtt_port,
        success=connected,
        latency_ms=latency if connected else latency,
        error=error_msg,
    )


def _check_tb_direct(config: TbDirectConfig) -> ConnectivityResult:
    """Test Mode B connectivity — direct TB PE."""
    connected = False
    error_msg = None
    start = time.monotonic()

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal connected
        if reason_code == 0:
            connected = True

    def on_disconnect(client, userdata, flags, reason_code, properties):
        pass

    client = None
    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"iot-sim-check-{int(time.time())}",
            transport="tcp",
        )

        if config.tb_use_tls:
            client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            client.tls_insecure_set(False)

        client.username_pw_set(config.tb_token, "")
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        client.connect(config.tb_host, config.tb_port, keepalive=5)
        client.loop_start()

        for _ in range(50):
            if connected:
                break
            time.sleep(0.1)

        latency = round((time.monotonic() - start) * 1000, 1)

    except Exception as e:
        error_msg = str(e)
        latency = round((time.monotonic() - start) * 1000, 1)
    finally:
        if client:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass

    return ConnectivityResult(
        mode="tb_direct",
        host=config.tb_host,
        port=config.tb_port,
        success=connected,
        latency_ms=latency if connected else latency,
        error=error_msg,
    )
