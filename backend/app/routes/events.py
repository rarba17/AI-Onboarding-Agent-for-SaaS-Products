"""
Event ingestion route.
POST /api/v1/events — receives batched events, pushes to Redis Stream.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.app.models.events import EventBatch, EventResponse
from backend.app.services.auth_service import validate_api_key
from backend.app.db.redis_client import get_async_redis
from backend.app.db.supabase_client import get_db
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.post("/events", response_model=EventResponse, status_code=202)
async def ingest_events(
    batch: EventBatch,
    company: dict = Depends(validate_api_key),
):
    """
    Receive batched user events from the SDK.
    Validates via Pydantic, pushes to Redis Stream, returns 202 immediately.
    Also stores events in PostgreSQL for persistence.
    """
    redis = await get_async_redis()
    db = get_db()
    company_id = company["company_id"]

    try:
        for event in batch.events:
            # Push to Redis Stream for real-time processing by AI worker
            event_data = {
                "user_id": event.user_id,
                "session_id": event.session_id,
                "event_type": event.event_type,
                "target_element_id": event.target_element_id or "",
                "timestamp": event.timestamp.isoformat(),
                "metadata": json.dumps(event.metadata or {}),
                "company_id": company_id,
            }
            await redis.xadd("events_stream", event_data)

            # Update session state in Redis
            session_key = f"session:{event.user_id}"
            await redis.hset(session_key, mapping={
                "last_event": event.event_type,
                "last_timestamp": event.timestamp.isoformat(),
                "session_id": event.session_id,
                "company_id": company_id,
            })
            await redis.expire(session_key, 3600)  # 1 hour TTL

            # Persist to PostgreSQL
            # Upsert session
            db.table("sessions").upsert({
                "session_id": event.session_id,
                "user_id": event.user_id,
                "company_id": company_id,
                "last_seen_time": event.timestamp.isoformat(),
                "is_active": True,
            }).execute()

            # Insert event
            db.table("events").insert({
                "user_id": event.user_id,
                "company_id": company_id,
                "session_id": event.session_id,
                "event_type": event.event_type,
                "target_element": event.target_element_id,
                "timestamp": event.timestamp.isoformat(),
                "properties": event.metadata or {},
            }).execute()

        return EventResponse(status="accepted", events_received=len(batch.events))

    except Exception as e:
        logger.error(f"Event ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process events")
