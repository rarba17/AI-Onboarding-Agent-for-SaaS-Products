"""
Escalation Agent — Drafts CSM alerts when nudges aren't working.
Triggered when nudge counter exceeds the threshold.
"""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

logger = logging.getLogger(__name__)

ESCALATION_SYSTEM_PROMPT = """You are a Customer Success assistant. A user is stuck and automated nudges have not helped.

Write a concise alert for a Customer Success Manager (CSM). Include:
1. A brief summary of the problem
2. What was tried (nudges sent)
3. A recommended action for the CSM

Keep it professional and under 150 words.

Output ONLY valid JSON:
{
    "subject": "Alert: User needs help with [area]",
    "body": "Your concise alert message here",
    "priority": "high" | "medium" | "low"
}"""


def get_llm():
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


async def run_escalation(
    user_id: str,
    company_id: str,
    diagnosis: dict,
    nudge_history: list[dict],
    db_client,
    webhook_url: str = None,
) -> dict:
    """
    Draft and send an escalation alert.

    Args:
        user_id: The stuck user
        company_id: Company context
        diagnosis: Latest diagnosis
        nudge_history: Previous nudges sent for this stuck point
        db_client: Supabase client
        webhook_url: Optional Slack webhook URL

    Returns:
        Escalation result
    """
    llm = get_llm()

    # Format nudge history
    nudge_summary = []
    for n in nudge_history[-5:]:  # Last 5 nudges
        nudge_summary.append(
            f"- [{n.get('nudge_type', '?')}] {n.get('content', '?')[:80]}... "
            f"(sent: {n.get('sent_at', '?')}, status: {n.get('status', '?')})"
        )

    user_prompt = f"""A user needs escalation to a human CSM:

**User ID:** {user_id}
**Stuck Point:** {diagnosis.get('stuck_point', 'unknown')}
**Reason:** {diagnosis.get('inferred_reason', 'unknown')}
**Nudges Sent (not effective):**
{chr(10).join(nudge_summary) if nudge_summary else 'No previous nudges recorded'}

Draft an alert for the CSM."""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=ESCALATION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        alert = json.loads(response.content)

        # Save escalation to database
        escalation_record = {
            "user_id": user_id,
            "company_id": company_id,
            "stuck_point": diagnosis.get("stuck_point"),
            "inferred_reason": diagnosis.get("inferred_reason"),
            "nudge_log": nudge_history[-5:],
            "status": "open",
        }
        db_result = db_client.table("escalations").insert(escalation_record).execute()
        escalation_id = db_result.data[0]["id"] if db_result.data else None

        logger.info(f"Escalation created: id={escalation_id} for user={user_id}")

        # Send webhook if configured
        if webhook_url:
            try:
                async with httpx.AsyncClient() as client:
                    slack_payload = {
                        "text": f"🚨 *{alert.get('subject', 'User Escalation')}*\n\n{alert.get('body', '')}",
                    }
                    await client.post(webhook_url, json=slack_payload)
                    logger.info(f"Webhook sent for escalation {escalation_id}")
            except Exception as e:
                logger.error(f"Webhook delivery failed: {e}")

        return {
            "escalation_id": escalation_id,
            "alert": alert,
            "webhook_sent": webhook_url is not None,
        }

    except Exception as e:
        logger.error(f"Escalation Agent error: {e}")
        # Still create a basic escalation record
        db_client.table("escalations").insert({
            "user_id": user_id,
            "company_id": company_id,
            "stuck_point": diagnosis.get("stuck_point", "unknown"),
            "inferred_reason": f"Escalation drafting failed: {str(e)}",
            "nudge_log": nudge_history[-5:],
            "status": "open",
        }).execute()
        return {"escalation_id": None, "error": str(e)}
