"""
Coach Agent — Generates personalized nudge content based on diagnosis and tone settings.
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

COACH_SYSTEM_PROMPT = """You are a friendly, expert onboarding coach for a B2B SaaS product.

Your job is to write a SHORT, helpful nudge message that will guide a stuck user to their next step.

Rules:
1. Be concise — max 2 sentences for tooltips, max 3 for chat messages.
2. Be specific — reference the exact feature or step the user is stuck on.
3. Be encouraging — never make the user feel bad for being stuck.
4. Match the tone/voice settings provided.
5. Suggest a concrete next action.

Output ONLY valid JSON in this exact format:
{
    "nudge_type": "tooltip" | "in_app_chat" | "email_draft",
    "content": "Your helpful nudge message here",
    "target_element_id": "element_id_to_attach_tooltip_to_or_null"
}

Choose nudge_type based on:
- "tooltip": for UI-specific confusion (attach to the confusing element)
- "in_app_chat": for general workflow confusion or multi-step guidance
- "email_draft": only if the user has been away for >10 minutes"""


def get_llm():
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.7,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


async def run_coach(
    diagnosis: dict,
    tone_settings: dict,
    user_context: dict = None,
) -> dict:
    """
    Generate a personalized nudge based on the diagnosis.

    Args:
        diagnosis: Output from the Diagnosis Agent
        tone_settings: Company's tone/voice configuration
        user_context: Optional additional context about the user

    Returns:
        Nudge dict with nudge_type, content, target_element_id
    """
    llm = get_llm()

    tone_desc = (
        f"Voice: {tone_settings.get('voice', 'friendly')}, "
        f"Formality: {tone_settings.get('formality', 'casual')}, "
        f"Use emoji: {'yes' if tone_settings.get('emoji', True) else 'no'}"
    )

    user_prompt = f"""Generate a nudge for this stuck user:

**Diagnosis:**
- Stuck at: {diagnosis.get('stuck_point', 'unknown')}
- Reason: {diagnosis.get('inferred_reason', 'unknown')}
- Confidence: {diagnosis.get('confidence_score', 0)}

**Tone Settings:** {tone_desc}

**Additional Context:** {json.dumps(user_context or {})}

Generate the nudge as JSON."""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=COACH_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        nudge = json.loads(response.content)
        nudge["stuck_point"] = diagnosis.get("stuck_point", "unknown")
        logger.info(f"Coach generated nudge: type={nudge.get('nudge_type')}")
        return nudge

    except json.JSONDecodeError as e:
        logger.error(f"Coach LLM returned invalid JSON: {e}")
        return {
            "nudge_type": "in_app_chat",
            "content": "Need some help? Try checking out the getting started guide!",
            "stuck_point": diagnosis.get("stuck_point", "unknown"),
            "target_element_id": None,
        }
    except Exception as e:
        logger.error(f"Coach Agent error: {e}")
        return {
            "nudge_type": "in_app_chat",
            "content": "Need some help? Try checking out the getting started guide!",
            "stuck_point": diagnosis.get("stuck_point", "unknown"),
            "target_element_id": None,
        }
