"""
Configuration routes for the admin dashboard.
Handles company settings, baselines, and data fetching.
"""

from fastapi import APIRouter, HTTPException, Depends
from backend.app.models.config import CompanyConfig, CompanyConfigUpdate, BaselineConfig
from backend.app.services.auth_service import get_current_admin
from backend.app.db.supabase_client import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


# ── Company Settings ──────────────────────────────────────────────

@router.get("/company")
async def get_company_config(admin: dict = Depends(get_current_admin)):
    """Get company configuration."""
    db = get_db()
    result = db.table("companies").select("*").eq("id", admin["company_id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")
    return result.data[0]


@router.patch("/company")
async def update_company_config(
    update: CompanyConfigUpdate,
    admin: dict = Depends(get_current_admin),
):
    """Update company configuration (partial update)."""
    db = get_db()
    update_data = update.model_dump(exclude_none=True)
    if update_data.get("tone_settings"):
        update_data["tone_settings"] = update.tone_settings.model_dump()

    result = db.table("companies").update(update_data).eq("id", admin["company_id"]).execute()
    return result.data[0] if result.data else {"status": "updated"}


# ── Baselines ─────────────────────────────────────────────────────

@router.get("/baselines")
async def list_baselines(admin: dict = Depends(get_current_admin)):
    """List all baselines for the company."""
    db = get_db()
    result = db.table("baselines").select("*").eq("company_id", admin["company_id"]).order("created_at").execute()
    return result.data


@router.post("/baselines")
async def create_baseline(
    baseline: BaselineConfig,
    admin: dict = Depends(get_current_admin),
):
    """Create a new success baseline."""
    db = get_db()
    result = db.table("baselines").insert({
        "company_id": admin["company_id"],
        "name": baseline.name,
        "event_sequence": [step.model_dump() for step in baseline.event_sequence],
        "is_active": baseline.is_active,
    }).execute()
    return result.data[0]


@router.put("/baselines/{baseline_id}")
async def update_baseline(
    baseline_id: str,
    baseline: BaselineConfig,
    admin: dict = Depends(get_current_admin),
):
    """Update an existing baseline."""
    db = get_db()
    result = db.table("baselines").update({
        "name": baseline.name,
        "event_sequence": [step.model_dump() for step in baseline.event_sequence],
        "is_active": baseline.is_active,
    }).eq("baseline_id", baseline_id).eq("company_id", admin["company_id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Baseline not found")
    return result.data[0]


@router.delete("/baselines/{baseline_id}")
async def delete_baseline(
    baseline_id: str,
    admin: dict = Depends(get_current_admin),
):
    """Delete a baseline."""
    db = get_db()
    db.table("baselines").delete().eq("baseline_id", baseline_id).eq("company_id", admin["company_id"]).execute()
    return {"status": "deleted"}


# ── Dashboard Data ────────────────────────────────────────────────

@router.get("/dashboard/funnel")
async def get_onboarding_funnel(admin: dict = Depends(get_current_admin)):
    """Get onboarding funnel data — count of users at each baseline step."""
    db = get_db()
    company_id = admin["company_id"]

    # Get the active baseline
    baseline_result = db.table("baselines").select("*").eq(
        "company_id", company_id
    ).eq("is_active", True).limit(1).execute()

    if not baseline_result.data:
        return {"steps": [], "message": "No active baseline defined"}

    baseline = baseline_result.data[0]
    steps = baseline.get("event_sequence", [])

    # For each step, count how many unique users completed it
    funnel_data = []
    for step in steps:
        event_type = step.get("event_type", "")
        count_result = db.table("events").select(
            "user_id", count="exact"
        ).eq("company_id", company_id).eq("event_type", event_type).execute()

        funnel_data.append({
            "step": step.get("label", event_type),
            "event_type": event_type,
            "users": count_result.count or 0,
        })

    return {"steps": funnel_data}


@router.get("/dashboard/sessions")
async def get_live_sessions(admin: dict = Depends(get_current_admin)):
    """Get active sessions for the company."""
    db = get_db()
    result = db.table("sessions").select("*").eq(
        "company_id", admin["company_id"]
    ).eq("is_active", True).order("last_seen_time", desc=True).limit(50).execute()
    return result.data


@router.get("/dashboard/nudges")
async def get_nudge_history(
    admin: dict = Depends(get_current_admin),
    limit: int = 50,
    offset: int = 0,
):
    """Get nudge history for the company."""
    db = get_db()
    result = db.table("nudges").select("*").eq(
        "company_id", admin["company_id"]
    ).order("sent_at", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.get("/dashboard/escalations")
async def get_escalations(admin: dict = Depends(get_current_admin)):
    """Get escalation queue for the company."""
    db = get_db()
    result = db.table("escalations").select("*").eq(
        "company_id", admin["company_id"]
    ).order("created_at", desc=True).execute()
    return result.data


@router.patch("/dashboard/escalations/{escalation_id}")
async def update_escalation(
    escalation_id: str,
    status: str,
    admin: dict = Depends(get_current_admin),
):
    """Update escalation status (open, in_progress, resolved, dismissed)."""
    db = get_db()
    update_data = {"status": status}
    if status == "resolved":
        from datetime import datetime, timezone
        update_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    if status == "in_progress":
        update_data["assigned_to"] = admin["user_id"]

    result = db.table("escalations").update(update_data).eq(
        "id", escalation_id
    ).eq("company_id", admin["company_id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return result.data[0]
