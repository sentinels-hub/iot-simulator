"""Mode A: MQTT transport via Nginx → Mosquitto.

Connects to Mosquitto through Nginx using WebSocket/TLS on port 443.
Publishes BSEC telemetry in the format consumed by TB Gateway's converter.

Auth: Anonymous (ClientID only, no username/password)
Topic: gw-lora-XXXX/bme680 (configurable)
"""

import json
import ssl
import logging
from typing import Optional

import paho.mqtt.client as mqtt

from ..models import MosquittoViaNginxConfig

logger = logging.getLogger(__name__)


class MosquittoTransport:
    """MQTT transport that publishes to Mosquitto via Nginx (Mode A)."""

    def __init__(self, config: MosquittoViaNginxConfig):
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._message_count = 0

    def connect(self) -> bool:
        """Establish MQTT connection to Mosquitto via Nginx."""
        protocol = mqtt.MQTTv311
        if self.config.mqtt_protocol.value == "websockets":
            # WebSocket transport through Nginx on port 443
            self.client = mqtt.Client(
                client_id=self.config.client_id,
                protocol=protocol,
                transport="websockets",
            )
            self.client.ws_set_options(path=self.config.mqtt_websocket_path)
        else:
            # Direct TCP (internal network only)
            self.client = mqtt.Client(
                client_id=self.config.client_id,
                protocol=protocol,
                transport="tcp",
            )

        if self.config.mqtt_use_tls:
            self.client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self.client.tls_insecure_set(False)

        # Anonymous auth — no username/password
        if self.config.mqtt_username:
            self.client.username_pw_set(
                self.config.mqtt_username, self.config.mqtt_password
            )

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

    def publish(self, payload: dict) -> bool:
        """Publish telemetry payload to Mosquitto topic."""
        if not self.client or not self.connected:
            logger.warning("Not connected, cannot publish")
            return False

        topic = self.config.mosquitto_topic
        message = json.dumps(payload)

        result = self.client.publish(topic, message, qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            self._message_count += 1
            logger.debug(f"Published to {topic}: {message[:100]}...")
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

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to Mosquitto at {self.config.mqtt_host}")
        else:
            logger.error(f"Mosquitto connection failed with rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected Mosquitto disconnect: rc={rc}")

    def _on_publish(self, client, userdata, mid):
        logger.debug(f"Message {mid} published successfully")
