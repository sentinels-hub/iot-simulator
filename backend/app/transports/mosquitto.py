"""Mode A: MQTT transport via Nginx → Mosquitto.

Connects to Mosquitto through Nginx using WebSocket/TLS on port 443.
Publishes BSEC telemetry in the format consumed by TB Gateway's converter.

Auth: Anonymous (ClientID only, no username/password)
Topic: gw-lora-XXXX/bme680 (configurable)

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

from ..models import MosquittoViaNginxConfig

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY_SECONDS = 5


class MosquittoTransport:
    """MQTT transport that publishes to Mosquitto via Nginx (Mode A)."""

    def __init__(self, config: MosquittoViaNginxConfig):
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._message_count = 0
        self._reconnect_attempts = 0
        self._reconnect_lock = threading.Lock()

    def connect(self) -> bool:
        """Establish MQTT connection to Mosquitto via Nginx."""
        # paho-mqtt v2: requires CallbackAPIVersion.VERSION2
        if self.config.mqtt_protocol.value == "websockets":
            self.client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id,
                transport="websockets",
            )
            # Explicit MQTT subprotocol header required by Mosquitto
            self.client.ws_set_options(
                path=self.config.mqtt_websocket_path,
                headers={"Sec-WebSocket-Protocol": "mqtt"},
            )
        else:
            self.client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id,
                transport="tcp",
            )

        if self.config.mqtt_use_tls:
            self.client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self.client.tls_insecure_set(False)

        # Anonymous auth — no username/password unless configured
        if self.config.mqtt_username:
            self.client.username_pw_set(self.config.mqtt_username, self.config.mqtt_password)

        # v2 callback signatures: (client, userdata, flags, reason_code, properties)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        try:
            self.client.connect(
                self.config.mqtt_host,
                self.config.mqtt_port,
                keepalive=60,
            )
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Mosquitto: {e}")
            return False

    def publish(self, payload: dict, topic: str | None = None) -> bool:
        """Publish telemetry payload to Mosquitto topic.

        Args:
            payload: JSON-serializable dict.
            topic: Override topic. Falls back to config default.
        """
        if not self.client or not self.connected:
            logger.warning("Not connected, cannot publish")
            return False

        publish_topic = topic or self.config.mosquitto_topic
        message = json.dumps(payload)

        result = self.client.publish(publish_topic, message, qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self._message_count += 1
            logger.debug(f"Published to {publish_topic}: {message[:100]}...")
            return True
        else:
            logger.error(f"Publish failed with rc={result.rc}")
            return False

    def disconnect(self):
        """Disconnect from Mosquitto."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    @property
    def message_count(self) -> int:
        return self._message_count

    # ─── paho-mqtt v2 callbacks ────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """v2 on_connect callback — reason_code is 0 on success."""
        if reason_code == 0 or str(reason_code) == "Success":
            self.connected = True
            self._reconnect_attempts = 0
            logger.info(f"Connected to Mosquitto at {self.config.mqtt_host}")
        else:
            logger.error(f"Mosquitto connection failed: reason_code={reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code=None, properties=None):
        """v2 on_disconnect callback — auto-reconnect on unexpected disconnect."""
        self.connected = False
        if reason_code != 0 and reason_code is not None:
            logger.warning(f"Unexpected Mosquitto disconnect: reason_code={reason_code}")
            self._attempt_reconnect()

    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        logger.debug(f"Message {mid} published successfully")

    # ─── Reconnect logic ───────────────────────────────────────────────────

    def _attempt_reconnect(self):
        """Attempt reconnection with exponential backoff."""
        with self._reconnect_lock:
            if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error(
                    f"Max reconnect attempts ({MAX_RECONNECT_ATTEMPTS}) reached — giving up"
                )
                return

            self._reconnect_attempts += 1
            attempt = self._reconnect_attempts
            logger.info(f"Reconnect attempt {attempt}/{MAX_RECONNECT_ATTEMPTS}...")

        # Reconnect in background thread to avoid blocking
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
                logger.info(f"Reconnected to Mosquitto on attempt {attempt}")
        except Exception as e:
            logger.error(f"Reconnect attempt {attempt} failed: {e}")
            self._attempt_reconnect()
