"""Mode B: Direct MQTT transport to ThingsBoard PE.

Connects directly to ThingsBoard PE using the gateway access token.
Publishes telemetry in the v1/gateway/telemetry format which auto-creates
child devices.

Auth: Access token as MQTT username
Topic: v1/gateway/telemetry

Uses paho-mqtt v2 API with CallbackAPIVersion.VERSION2.
Reconnect logic: on unexpected disconnect, retry every 5s up to 10 times.
"""

import json
import logging
import ssl
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from ..models import TbDirectConfig

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY_SECONDS = 5


class TbDirectTransport:
    """MQTT transport that publishes directly to ThingsBoard PE (Mode B)."""

    def __init__(self, config: TbDirectConfig):
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._message_count = 0
        self._reconnect_attempts = 0
        self._reconnect_lock = threading.Lock()

    def connect(self) -> bool:
        """Establish MQTT connection to ThingsBoard PE."""
        # paho-mqtt v2: requires CallbackAPIVersion.VERSION2
        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"iot-sim-{id(self)}",
            transport="tcp",
        )

        # TLS for port 443
        if self.config.tb_use_tls:
            self.client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self.client.tls_insecure_set(False)

        # Access token as MQTT username, empty password
        self.client.username_pw_set(self.config.tb_token, "")

        # v2 callback signatures: (client, userdata, flags, reason_code, properties)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        try:
            self.client.connect(
                self.config.tb_host,
                self.config.tb_port,
                keepalive=60,
            )
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to ThingsBoard PE: {e}")
            return False

    def publish_gateway_telemetry(
        self, gateway_name: str, devices: dict[str, list[dict]]
    ) -> bool:
        """Publish telemetry in v1/gateway/telemetry format.

        Args:
            gateway_name: Gateway device name in TB (e.g. 'gw-iot-direct-ingest')
            devices: Dict mapping device names to list of telemetry dicts.
                     Format: { "BME680_SN_001": [{ "ts": ..., "values": {...} }] }
        """
        if not self.client or not self.connected:
            logger.warning("Not connected to TB PE, cannot publish")
            return False

        payload = dict(devices)
        message = json.dumps(payload)
        result = self.client.publish(self.config.tb_topic, message, qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self._message_count += 1
            logger.info(f"Published gateway telemetry to TB: {len(devices)} devices")
            return True
        else:
            logger.error(f"TB publish failed with rc={result.rc}")
            return False

    def disconnect(self):
        """Disconnect from ThingsBoard PE."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    @property
    def message_count(self) -> int:
        return self._message_count

    # ─── paho-mqtt v2 callbacks ────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """v2 on_connect callback."""
        if reason_code == 0 or str(reason_code) == "Success":
            self.connected = True
            self._reconnect_attempts = 0
            logger.info(f"Connected to ThingsBoard PE at {self.config.tb_host}")
        else:
            logger.error(f"TB PE connection failed: reason_code={reason_code}")

    def _on_disconnect(
        self, client, userdata, flags, reason_code=None, properties=None
    ):
        """v2 on_disconnect callback — auto-reconnect on unexpected disconnect."""
        self.connected = False
        if reason_code != 0 and reason_code is not None:
            logger.warning(f"Unexpected TB PE disconnect: reason_code={reason_code}")
            self._attempt_reconnect()

    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        logger.debug(f"TB message {mid} published successfully")

    # ─── Reconnect logic ───────────────────────────────────────────────────

    def _attempt_reconnect(self):
        """Attempt reconnection with backoff."""
        with self._reconnect_lock:
            if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error(
                    f"Max reconnect attempts ({MAX_RECONNECT_ATTEMPTS}) reached — giving up"
                )
                return

            self._reconnect_attempts += 1
            attempt = self._reconnect_attempts
            logger.info(f"Reconnect attempt {attempt}/{MAX_RECONNECT_ATTEMPTS}...")

        threading.Thread(
            target=self._reconnect_worker,
            args=(attempt,),
            daemon=True,
        ).start()

    def _reconnect_worker(self, attempt: int):
        """Background reconnect worker."""
        time.sleep(RECONNECT_DELAY_SECONDS)
        try:
            if self.client:
                self.client.reconnect()
                logger.info(f"Reconnected to TB PE on attempt {attempt}")
        except Exception as e:
            logger.error(f"Reconnect attempt {attempt} failed: {e}")
            self._attempt_reconnect()
