"""
Pydantic models for configuration and admin schemas.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class ToneSettings(BaseModel):
    """Tone and voice configuration for the Coach Agent."""
    voice: str = Field(default="friendly", description="Voice style: friendly, professional, casual")
    formality: str = Field(default="casual", description="Formality level: formal, casual, neutral")
    emoji: bool = Field(default=True, description="Whether to include emoji in nudges")


class CompanyConfig(BaseModel):
    """Company configuration."""
    name: str
    tone_settings: ToneSettings = Field(default_factory=ToneSettings)
    escalation_threshold: int = Field(default=3, ge=1, le=10)


class CompanyConfigUpdate(BaseModel):
    """Partial update for company config."""
    name: Optional[str] = None
    tone_settings: Optional[ToneSettings] = None
    escalation_threshold: Optional[int] = Field(None, ge=1, le=10)


class BaselineStep(BaseModel):
    """A single step in a success baseline."""
    event_type: str
    target_element_id: Optional[str] = None
    label: str = ""
    order: int = 0


class BaselineConfig(BaseModel):
    """Success baseline definition."""
    name: str = "Default Baseline"
    event_sequence: list[BaselineStep] = []
    is_active: bool = True


class AdminUserCreate(BaseModel):
    """Schema for creating an admin user."""
    email: str
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    role: str = Field(default="admin")


class AdminUserLogin(BaseModel):
    """Schema for admin login."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    company_id: str
    role: str
