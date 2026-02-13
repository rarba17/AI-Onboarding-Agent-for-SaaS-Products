"""
Diagnosis Agent — Analyzes user session to identify stuck points.
Fetches session history, compares against success baseline, and prompts LLM for structured diagnosis.
"""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

logger = logging.getLogger(__name__)

DIAGNOSIS_SYSTEM_PROMPT = """You are an expert User Experience Analyst for B2B SaaS products.

Your job is to analyze a user's event stream during their onboarding session and compare it against the "Success Baseline" — the ideal path a successful user takes.

You must identify:
1. WHERE the user is stuck (the specific step or screen)
2. WHY they appear to be stuck (inferred from their behavior patterns)
3. How CONFIDENT you are in your diagnosis (0.0 to 1.0)

Output ONLY valid JSON in this exact format:
{
    "stuck_point": "descriptive name of where user is stuck",
    "inferred_reason": "clear explanation of why the user appears stuck based on their behavior",
    "confidence_score": 0.85
}

Key behavioral signals to look for:
- Repeated visits to the same page without progression
- Long inactivity periods on a specific step
- Clicking help/cancel/back buttons
- Hovering or interacting with elements without completing actions
- Skipping expected steps in the baseline

If the user appears to be progressing normally, set confidence_score below 0.3."""


def get_llm():
    """Get the configured LLM instance."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


async def run_diagnosis(
    user_id: str,
    session_events: list[dict],
    baseline_sequence: list[dict],
    session_state: dict,
) -> dict:
    """
    Analyze user session and return a structured diagnosis.

    Args:
        user_id: The user being analyzed
        session_events: List of events from the current session
        baseline_sequence: The success baseline event sequence
        session_state: Current session state from Redis

    Returns:
        Diagnosis dict with stuck_point, inferred_reason, confidence_score
    """
    llm = get_llm()

    # Format the user's event stream
    event_summary = []
    for e in session_events[-30:]:  # Last 30 events to keep context window manageable
        event_summary.append(
            f"[{e.get('timestamp', '?')}] {e.get('event_type', '?')} "
            f"on '{e.get('target_element', 'unknown')}' "
            f"| metadata: {json.dumps(e.get('properties', {}))}"
        )

    # Format the baseline
    baseline_summary = " → ".join(
        [f"{step.get('label', step.get('event_type', '?'))}" for step in baseline_sequence]
    )

    user_prompt = f"""Analyze this user's onboarding session:

**User ID:** {user_id}
**Session Duration:** {session_state.get('duration_minutes', 'unknown')} minutes
**Last Event:** {session_state.get('last_event', 'unknown')}

**Success Baseline (expected path):**
{baseline_summary}

**User's Event Stream (most recent last):**
{chr(10).join(event_summary)}

Provide your diagnosis as JSON."""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=DIAGNOSIS_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        diagnosis = json.loads(response.content)
        logger.info(
            f"Diagnosis for user={user_id}: "
            f"stuck_point='{diagnosis.get('stuck_point')}' "
            f"confidence={diagnosis.get('confidence_score')}"
        )
        return diagnosis

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return {"stuck_point": "unknown", "inferred_reason": "Diagnosis failed — invalid LLM response", "confidence_score": 0.0}
    except Exception as e:
        logger.error(f"Diagnosis Agent error: {e}")
        return {"stuck_point": "unknown", "inferred_reason": f"Diagnosis failed: {str(e)}", "confidence_score": 0.0}
