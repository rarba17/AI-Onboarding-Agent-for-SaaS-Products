"""
Pydantic models for event-related schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class EventPayload(BaseModel):
    """Single event from the client SDK."""
    user_id: str = Field(..., description="Unique identifier for the user")
    session_id: str = Field(..., description="Current session identifier")
    event_type: str = Field(..., description="Type of event: click, page_view, input_change, etc.")
    target_element_id: Optional[str] = Field(None, description="DOM element ID that was interacted with")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class EventBatch(BaseModel):
    """Batched events from the client SDK."""
    api_key: str = Field(..., description="API key for authentication")
    events: list[EventPayload] = Field(..., min_length=1, max_length=50)


class EventResponse(BaseModel):
    """Response after accepting events."""
    status: str = "accepted"
    events_received: int = 0
