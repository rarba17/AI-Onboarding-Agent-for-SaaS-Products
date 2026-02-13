"""
Redis Stream Consumer / Worker
Reads events from the Redis 'events_stream', updates session state,
and triggers the LangGraph workflow when stuck signals are detected.
"""

import asyncio
import json
import logging
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared_config import settings

from backend.app.db.redis_client import get_sync_redis
from backend.app.db.supabase_client import get_db
from ai_core.workflow import onboarding_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────

INACTIVITY_THRESHOLD_SECONDS = 120  # 2 minutes
STUCK_EVENT_TYPES = {"help_click", "cancel_click", "back_click", "error_encountered"}
CONSUMER_GROUP = "ai_workers"
CONSUMER_NAME = "worker_1"
STREAM_KEY = "events_stream"


# ── Helper Functions ──────────────────────────────────────────────

def should_trigger_workflow(event: dict, redis_client) -> bool:
    """
    Determine if this event should trigger the AI workflow.
    Triggers on:
    1. Stuck events (help, cancel, back, error)
    2. Inactivity detection (checked separately via session state)
    """
    event_type = event.get("event_type", "")

    # Direct stuck signals
    if event_type in STUCK_EVENT_TYPES:
        logger.info(f"Stuck event detected: {event_type} for user={event.get('user_id')}")
        return True

    # Check for inactivity
    user_id = event.get("user_id", "")
    session_key = f"session:{user_id}"
    last_ts = redis_client.hget(session_key, "last_timestamp")

    if last_ts:
        try:
            from datetime import datetime, timezone
            last_time = datetime.fromisoformat(last_ts)
            now = datetime.now(timezone.utc)
            if last_time.tzinfo is None:
                from datetime import timezone as tz
                last_time = last_time.replace(tzinfo=tz.utc)
            elapsed = (now - last_time).total_seconds()
            if elapsed > INACTIVITY_THRESHOLD_SECONDS:
                logger.info(f"Inactivity detected for user={user_id}: {elapsed:.0f}s")
                return True
        except Exception:
            pass

    return False


async def trigger_workflow(user_id: str, company_id: str, session_id: str, db, redis_client):
    """Fetch context and run the LangGraph workflow."""
    try:
        # Get session events from PostgreSQL
        events_result = db.table("events").select("*").eq(
            "user_id", user_id
        ).eq("session_id", session_id).order("timestamp").execute()
        session_events = events_result.data or []

        # Get active baseline
        baseline_result = db.table("baselines").select("*").eq(
            "company_id", company_id
        ).eq("is_active", True).limit(1).execute()
        baseline_sequence = baseline_result.data[0]["event_sequence"] if baseline_result.data else []

        # Get company config
        company_result = db.table("companies").select("*").eq("id", company_id).execute()
        company_config = company_result.data[0] if company_result.data else {}

        # Get session state from Redis
        session_key = f"session:{user_id}"
        session_state = redis_client.hgetall(session_key)

        # Build initial state
        initial_state = {
            "user_id": user_id,
            "company_id": company_id,
            "session_id": session_id,
            "session_events": session_events,
            "baseline_sequence": baseline_sequence,
            "session_state": session_state,
            "tone_settings": company_config.get("tone_settings", {}),
            "escalation_threshold": company_config.get("escalation_threshold", 3),
            "diagnosis": None,
            "nudge": None,
            "action_result": None,
            "escalation_result": None,
            "completed": False,
            "error": None,
        }

        # Run the workflow
        logger.info(f"🚀 Triggering workflow for user={user_id}, session={session_id}")
        result = await onboarding_workflow.ainvoke(initial_state)
        logger.info(f"✅ Workflow complete for user={user_id}: diagnosis={result.get('diagnosis', {}).get('stuck_point', 'N/A')}")

        return result

    except Exception as e:
        logger.error(f"Workflow trigger failed for user={user_id}: {e}")
        return None


# ── Main Consumer Loop ────────────────────────────────────────────

async def run_worker():
    """Main worker loop — consumes events from Redis Stream and triggers AI workflows."""
    import redis as sync_redis_lib

    redis_client = get_sync_redis()
    db = get_db()

    # Create consumer group (if not exists)
    try:
        redis_client.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(f"Created consumer group '{CONSUMER_GROUP}'")
    except sync_redis_lib.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info(f"Consumer group '{CONSUMER_GROUP}' already exists")
        else:
            raise

    logger.info("🟢 AI Worker started — listening for events...")

    while True:
        try:
            # Read new messages from the stream
            messages = redis_client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_KEY: ">"},
                count=10,
                block=5000,  # Block for 5 seconds
            )

            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, data in entries:
                    try:
                        # Check if this event should trigger the workflow
                        if should_trigger_workflow(data, redis_client):
                            await trigger_workflow(
                                user_id=data.get("user_id", ""),
                                company_id=data.get("company_id", ""),
                                session_id=data.get("session_id", ""),
                                db=db,
                                redis_client=redis_client,
                            )

                        # Acknowledge the message
                        redis_client.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)

                    except Exception as e:
                        logger.error(f"Error processing message {msg_id}: {e}")

        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5)  # Back off on errors


if __name__ == "__main__":
    asyncio.run(run_worker())
