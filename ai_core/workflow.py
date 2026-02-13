"""
LangGraph Workflow — Multi-agent onboarding system.

Defines the StateGraph that orchestrates:
  Diagnosis Agent → Decision Router → Coach Agent → Action Taker → Escalation Agent (conditional)
"""

import logging
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_core.agents.diagnosis import run_diagnosis
from ai_core.agents.coach import run_coach
from ai_core.agents.action import run_action
from ai_core.agents.escalation import run_escalation

logger = logging.getLogger(__name__)


# ── State Schema ──────────────────────────────────────────────────

class OnboardingState(TypedDict):
    """State passed through the LangGraph workflow."""
    # Input
    user_id: str
    company_id: str
    session_id: str
    session_events: list[dict]
    baseline_sequence: list[dict]
    session_state: dict
    tone_settings: dict
    escalation_threshold: int

    # Intermediate
    diagnosis: Optional[dict]
    nudge: Optional[dict]
    action_result: Optional[dict]

    # Output
    escalation_result: Optional[dict]
    completed: bool
    error: Optional[str]


# ── Node Functions ────────────────────────────────────────────────

async def diagnosis_node(state: OnboardingState) -> dict:
    """Node 1: Run the Diagnosis Agent."""
    try:
        diagnosis = await run_diagnosis(
            user_id=state["user_id"],
            session_events=state["session_events"],
            baseline_sequence=state["baseline_sequence"],
            session_state=state["session_state"],
        )
        return {"diagnosis": diagnosis}
    except Exception as e:
        logger.error(f"Diagnosis node failed: {e}")
        return {"diagnosis": None, "error": str(e), "completed": True}


async def coach_node(state: OnboardingState) -> dict:
    """Node 3: Run the Coach Agent."""
    try:
        nudge = await run_coach(
            diagnosis=state["diagnosis"],
            tone_settings=state["tone_settings"],
            user_context={"user_id": state["user_id"], "session_id": state["session_id"]},
        )
        return {"nudge": nudge}
    except Exception as e:
        logger.error(f"Coach node failed: {e}")
        return {"nudge": None, "error": str(e), "completed": True}


async def action_node(state: OnboardingState) -> dict:
    """Node 4: Run the Action Taker."""
    from backend.app.db.supabase_client import get_db
    from backend.app.db.redis_client import get_async_redis

    try:
        redis = await get_async_redis()
        db = get_db()

        action_result = await run_action(
            user_id=state["user_id"],
            company_id=state["company_id"],
            session_id=state["session_id"],
            nudge=state["nudge"],
            diagnosis=state["diagnosis"],
            redis_client=redis,
            db_client=db,
        )
        return {"action_result": action_result}
    except Exception as e:
        logger.error(f"Action node failed: {e}")
        return {"action_result": None, "error": str(e), "completed": True}


async def escalation_node(state: OnboardingState) -> dict:
    """Node 5: Run the Escalation Agent (conditional)."""
    from backend.app.db.supabase_client import get_db

    try:
        db = get_db()

        # Fetch recent nudge history for this user + stuck point
        stuck_point = state["diagnosis"].get("stuck_point", "unknown")
        nudge_result = db.table("nudges").select("*").eq(
            "user_id", state["user_id"]
        ).eq("stuck_point", stuck_point).order("sent_at", desc=True).limit(5).execute()

        escalation_result = await run_escalation(
            user_id=state["user_id"],
            company_id=state["company_id"],
            diagnosis=state["diagnosis"],
            nudge_history=nudge_result.data or [],
            db_client=db,
        )
        return {"escalation_result": escalation_result, "completed": True}
    except Exception as e:
        logger.error(f"Escalation node failed: {e}")
        return {"escalation_result": None, "error": str(e), "completed": True}


# ── Routing Functions ─────────────────────────────────────────────

def should_proceed_to_coach(state: OnboardingState) -> str:
    """Decision Router: check confidence threshold."""
    diagnosis = state.get("diagnosis")
    if not diagnosis:
        return "end"

    confidence = diagnosis.get("confidence_score", 0)
    if confidence >= 0.6:
        logger.info(f"Confidence {confidence} >= 0.6 — proceeding to Coach")
        return "coach"
    else:
        logger.info(f"Confidence {confidence} < 0.6 — ending (user likely fine)")
        return "end"


def should_escalate(state: OnboardingState) -> str:
    """Check if nudge counter exceeds escalation threshold."""
    action_result = state.get("action_result", {})
    threshold = state.get("escalation_threshold", 3)
    nudge_count = action_result.get("nudge_count", 0)

    if nudge_count > threshold:
        logger.info(f"Nudge count {nudge_count} > threshold {threshold} — escalating")
        return "escalate"
    else:
        return "end"


# ── Build the Graph ───────────────────────────────────────────────

def build_workflow() -> StateGraph:
    """Build and compile the LangGraph workflow."""

    workflow = StateGraph(OnboardingState)

    # Add nodes
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("coach", coach_node)
    workflow.add_node("action", action_node)
    workflow.add_node("escalation", escalation_node)

    # Set entry point
    workflow.set_entry_point("diagnosis")

    # Decision router after diagnosis
    workflow.add_conditional_edges(
        "diagnosis",
        should_proceed_to_coach,
        {"coach": "coach", "end": END},
    )

    # Coach → Action
    workflow.add_edge("coach", "action")

    # Conditional escalation after action
    workflow.add_conditional_edges(
        "action",
        should_escalate,
        {"escalate": "escalation", "end": END},
    )

    # Escalation → END
    workflow.add_edge("escalation", END)

    return workflow.compile()


# Compiled workflow — importable
onboarding_workflow = build_workflow()
