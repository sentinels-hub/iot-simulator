"""WebSocket endpoint for live log streaming.

Streams simulation log entries in real-time to connected clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..api.simulations import simulations

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/api/simulations/{sim_id}/logs/stream")
async def log_stream(websocket: WebSocket, sim_id: str):
    """Stream simulation log entries in real-time via WebSocket.

    Connects to an active simulation and forwards new log entries
    as they are generated. Falls back to polling if no new entries.
    """
    await websocket.accept()

    engine = simulations.get(sim_id)
    if not engine:
        await websocket.send_json({"error": f"Simulation {sim_id} not found"})
        await websocket.close()
        return

    last_index = len(engine.state.logs)
    last_status = engine.state.status.value

    try:
        while True:
            # Check for new log entries
            current_logs = engine.state.logs
            if len(current_logs) > last_index:
                for entry in current_logs[last_index:]:
                    await websocket.send_json({"type": "log", "data": entry})
                last_index = len(current_logs)

            # Check for status changes
            current_status = engine.state.status.value
            if current_status != last_status:
                await websocket.send_json({"type": "status", "data": current_status})
                last_status = current_status

            # Send heartbeat with current metrics
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "data": {
                        "messages_sent": engine.state.messages_sent,
                        "errors": len(engine.state.errors),
                        "status": current_status,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }
            )

            # Also send latest telemetry preview
            if engine.state.last_telemetry:
                # Truncate for WebSocket payload size
                preview = str(engine.state.last_telemetry)[:500]
                await websocket.send_json(
                    {
                        "type": "telemetry",
                        "data": preview,
                    }
                )

            await asyncio.sleep(1)  # Poll every second

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from simulation {sim_id}")
    except Exception as e:
        logger.error(f"WebSocket error for simulation {sim_id}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
