"""Mode B: Direct MQTT transport to ThingsBoard PE.

Connects directly to ThingsBoard PE using the gateway access token.
Publishes telemetry in the v1/gateway/telemetry format which auto-creates
child devices.

Auth: Access token as MQTT username
Topic: v1/gateway/telemetry
"""

import json
import ssl
import logging
from typing import Optional

import paho.mqtt.client as mqtt

from ..models import TbDirectConfig

logger = logging.getLogger(__name__)


class TbDirectTransport:
    """MQTT transport that publishes directly to ThingsBoard PE (Mode B)."""

    def __init__(self, config: TbDirectConfig):
        self.config = config
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._message_count = 0

    def connect(self) -> bool:
        """Establish MQTT connection to ThingsBoard PE."""
        self.client = mqtt.Client(
            client_id=f"iot-sim-{id(self)}",
            protocol=mqtt.MQTTv311,
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

        The gateway_name is included as a key in the payload so TB registers
        the telemetry under both the gateway and child devices.
        """
        if not self.client or not self.connected:
            logger.warning("Not connected to TB PE, cannot publish")
            return False

        # Build gateway telemetry payload
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

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to ThingsBoard PE at {self.config.tb_host}")
        else:
            logger.error(f"TB PE connection failed with rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected TB PE disconnect: rc={rc}")

    def _on_publish(self, client, userdata, mid):
        logger.debug(f"TB message {mid} published successfully")
