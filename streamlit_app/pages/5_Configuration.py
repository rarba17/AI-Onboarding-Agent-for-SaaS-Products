"""
Configuration — Manage company settings: tone/voice, escalation thresholds, API keys.
"""

import streamlit as st
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .config-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e9ecef;
        margin-bottom: 1rem;
    }
</style>""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# ⚙️ Configuration")
st.markdown("Manage your AI onboarding agent settings.")

headers = {"Authorization": f"Bearer {st.session_state.token}"}
base_url = f"http://localhost:{settings.FASTAPI_PORT}"

# Fetch current config
try:
    resp = httpx.get(f"{base_url}/api/v1/config/company", headers=headers)
    company = resp.json() if resp.status_code == 200 else {}
except Exception:
    company = {}

col1, col2 = st.columns(2)

# ── Tone & Voice Settings ────────────────────────────────────────

with col1:
    st.subheader("🎤 Tone & Voice")
    st.caption("Configure how the AI coach communicates with your users.")

    tone = company.get("tone_settings", {})

    voice = st.selectbox(
        "Voice Style",
        ["friendly", "professional", "casual", "empathetic", "enthusiastic"],
        index=["friendly", "professional", "casual", "empathetic", "enthusiastic"].index(
            tone.get("voice", "friendly")
        ),
    )
    formality = st.selectbox(
        "Formality Level",
        ["casual", "neutral", "formal"],
        index=["casual", "neutral", "formal"].index(tone.get("formality", "casual")),
    )
    use_emoji = st.toggle("Include Emoji in Nudges", value=tone.get("emoji", True))

    st.markdown("**Preview:**")
    preview_styles = {
        ("friendly", "casual"): "Hey there! 👋 Looks like you're on the template step. The 'Blank Slate' is great for starting fresh!",
        ("professional", "formal"): "We noticed you may need assistance with template selection. The 'Blank Slate' option allows you to start from scratch.",
        ("casual", "casual"): "Stuck on templates? No worries! Try 'Blank Slate' to start clean 🎯",
        ("empathetic", "neutral"): "We understand choosing a template can feel overwhelming. 'Blank Slate' is a simple way to begin.",
    }
    preview = preview_styles.get(
        (voice, formality),
        f"This is a {voice}, {formality} nudge preview."
    )
    if not use_emoji:
        import re
        preview = re.sub(r'[^\w\s.,!?\'-]', '', preview)
    st.info(preview)

    if st.button("💾 Save Tone Settings", use_container_width=True, type="primary"):
        try:
            resp = httpx.patch(
                f"{base_url}/api/v1/config/company",
                headers=headers,
                json={
                    "tone_settings": {
                        "voice": voice,
                        "formality": formality,
                        "emoji": use_emoji,
                    }
                },
            )
            if resp.status_code == 200:
                st.success("✅ Tone settings saved!")
            else:
                st.error(f"Failed: {resp.text}")
        except Exception as e:
            st.error(f"Error: {e}")

# ── Escalation & General Settings ─────────────────────────────────

with col2:
    st.subheader("🚨 Escalation Settings")
    st.caption("Configure when stuck users should be escalated to a CSM.")

    threshold = st.slider(
        "Escalation Threshold",
        min_value=1,
        max_value=10,
        value=company.get("escalation_threshold", 3),
        help="Number of nudges before escalating to a human CSM",
    )

    st.markdown(f"After **{threshold}** unsuccessful nudges for the same stuck point, the user will be escalated to a CSM.")

    company_name = st.text_input("Company Name", value=company.get("name", ""))

    if st.button("💾 Save General Settings", use_container_width=True, type="primary"):
        try:
            update_data = {"escalation_threshold": threshold}
            if company_name:
                update_data["name"] = company_name
            resp = httpx.patch(
                f"{base_url}/api/v1/config/company",
                headers=headers,
                json=update_data,
            )
            if resp.status_code == 200:
                st.success("✅ Settings saved!")
            else:
                st.error(f"Failed: {resp.text}")
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")

    # API Keys
    st.subheader("🔑 API Keys")
    st.caption("Manage API keys for SDK integration.")

    try:
        keys_resp = httpx.get(f"{base_url}/api/v1/auth/api-keys", headers=headers)
        keys = keys_resp.json() if keys_resp.status_code == 200 else []
    except Exception:
        keys = []

    for key in keys:
        status = "🟢 Active" if key.get("is_active") else "🔴 Inactive"
        st.markdown(f"**{key.get('label', 'unnamed')}** — {status} — Created: {key.get('created_at', 'N/A')[:10]}")

    new_label = st.text_input("New Key Label", placeholder="production")
    if st.button("➕ Generate New API Key", use_container_width=True):
        try:
            resp = httpx.post(
                f"{base_url}/api/v1/auth/api-keys",
                headers=headers,
                params={"label": new_label or "default"},
            )
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"✅ New API Key: `{data['api_key']}`")
                st.warning("⚠️ Copy this key now — it won't be shown again!")
            else:
                st.error(f"Failed: {resp.text}")
        except Exception as e:
            st.error(f"Error: {e}")
