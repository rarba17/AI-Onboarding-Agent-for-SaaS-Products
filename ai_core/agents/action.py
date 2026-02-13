"""
Action Taker — Saves nudge to DB, increments counter, sends via WebSocket.
"""

import json
import logging
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

logger = logging.getLogger(__name__)


async def run_action(
    user_id: str,
    company_id: str,
    session_id: str,
    nudge: dict,
    diagnosis: dict,
    redis_client,
    db_client,
) -> dict:
    """
    Execute the nudge delivery:
    1. Save nudge to PostgreSQL
    2. Increment nudge counter in Redis
    3. Send nudge via WebSocket (through FastAPI)

    Returns:
        Action result with nudge_count and delivery status
    """
    stuck_point = nudge.get("stuck_point", "unknown")

    try:
        # 1. Save nudge to PostgreSQL
        nudge_record = {
            "user_id": user_id,
            "company_id": company_id,
            "session_id": session_id,
            "stuck_point": stuck_point,
            "nudge_type": nudge.get("nudge_type", "in_app_chat"),
            "content": nudge.get("content", ""),
            "diagnosis": diagnosis,
        }
        db_result = db_client.table("nudges").insert(nudge_record).execute()
        nudge_id = db_result.data[0]["nudge_id"] if db_result.data else None
        logger.info(f"Nudge saved to DB: nudge_id={nudge_id}")

        # 2. Increment nudge counter in Redis
        counter_key = f"nudge_count:{user_id}:{stuck_point}"
        count = await redis_client.incr(counter_key)
        await redis_client.expire(counter_key, 86400)  # 24 hour TTL
        logger.info(f"Nudge counter for user={user_id}, stuck={stuck_point}: {count}")

        # 3. Publish nudge for WebSocket delivery
        nudge_payload = {
            "type": "nudge",
            "nudge_id": nudge_id,
            "nudge_type": nudge.get("nudge_type"),
            "content": nudge.get("content"),
            "stuck_point": stuck_point,
            "target_element_id": nudge.get("target_element_id"),
        }

        # Publish to Redis pub/sub for the WebSocket server to pick up
        await redis_client.publish(f"nudges:{user_id}", json.dumps(nudge_payload))
        logger.info(f"Nudge published for user={user_id}")

        return {
            "nudge_id": nudge_id,
            "nudge_count": count,
            "delivered": True,
            "stuck_point": stuck_point,
        }

    except Exception as e:
        logger.error(f"Action Taker error: {e}")
        return {
            "nudge_id": None,
            "nudge_count": 0,
            "delivered": False,
            "stuck_point": stuck_point,
            "error": str(e),
        }
