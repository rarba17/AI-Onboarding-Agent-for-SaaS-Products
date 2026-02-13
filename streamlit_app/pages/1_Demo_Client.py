"""
Demo Client — Simulates a SaaS user journey.
Allows sending events and viewing real-time nudges.
"""

import streamlit as st
import httpx
import json
import time
import uuid
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Demo Client", page_icon="🎮", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .nudge-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin: 0.5rem 0;
        animation: slideIn 0.3s ease-out;
    }
    @keyframes slideIn {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    .event-log {
        background: #1a1a2e;
        color: #00ff88;
        padding: 1rem;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        max-height: 300px;
        overflow-y: auto;
    }
    .sim-button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# 🎮 Demo Client")
st.markdown("Simulate a user's onboarding journey — trigger events and see AI nudges in real-time.")

# ── Session Setup ─────────────────────────────────────────────────

if "demo_user_id" not in st.session_state:
    st.session_state.demo_user_id = f"demo_user_{uuid.uuid4().hex[:8]}"
    st.session_state.demo_session_id = f"session_{uuid.uuid4().hex[:8]}"
    st.session_state.event_log = []
    st.session_state.nudges_received = []

col1, col2 = st.columns(2)
with col1:
    st.session_state.demo_user_id = st.text_input("User ID", value=st.session_state.demo_user_id)
with col2:
    st.session_state.demo_session_id = st.text_input("Session ID", value=st.session_state.demo_session_id)

st.markdown("---")

# ── Event Simulation ─────────────────────────────────────────────

st.subheader("📤 Send Events")
st.caption("Click buttons to simulate user actions. Events are sent to the backend for AI processing.")

# First, get or create an API key for this company
if "demo_api_key" not in st.session_state:
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        resp = httpx.post(
            f"http://localhost:{settings.FASTAPI_PORT}/api/v1/auth/api-keys",
            params={"label": "demo"},
            headers=headers,
        )
        if resp.status_code == 200:
            st.session_state.demo_api_key = resp.json().get("api_key", "")
        else:
            st.session_state.demo_api_key = ""
    except Exception:
        st.session_state.demo_api_key = ""


def send_event(event_type: str, target: str = "", metadata: dict = None):
    """Send an event to the backend."""
    if not st.session_state.demo_api_key:
        st.error("No API key available. Please check backend connection.")
        return

    event = {
        "user_id": st.session_state.demo_user_id,
        "session_id": st.session_state.demo_session_id,
        "event_type": event_type,
        "target_element_id": target,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }

    try:
        resp = httpx.post(
            f"http://localhost:{settings.FASTAPI_PORT}/api/v1/events",
            json={
                "api_key": st.session_state.demo_api_key,
                "events": [event],
            },
            headers={"X-API-Key": st.session_state.demo_api_key},
        )
        status = "✅" if resp.status_code == 202 else f"❌ {resp.status_code}"
        st.session_state.event_log.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {status} {event_type} → {target or 'N/A'}"
        )
    except httpx.ConnectError:
        st.session_state.event_log.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection error"
        )


# Simulated Onboarding Journey
st.markdown("#### 🚶 Onboarding Journey Steps")
cols = st.columns(5)

with cols[0]:
    if st.button("👋 Signup", use_container_width=True, type="primary"):
        send_event("signup", "signup_form")
        st.toast("Event sent: signup")

with cols[1]:
    if st.button("📄 View Dashboard", use_container_width=True):
        send_event("page_view", "dashboard_page", {"page": "/dashboard"})
        st.toast("Event sent: page_view")

with cols[2]:
    if st.button("📁 Create Project", use_container_width=True):
        send_event("create_project", "new_project_button")
        st.toast("Event sent: create_project")

with cols[3]:
    if st.button("👥 Invite Team", use_container_width=True):
        send_event("invite_team", "invite_modal")
        st.toast("Event sent: invite_team")

with cols[4]:
    if st.button("✅ Complete Setup", use_container_width=True):
        send_event("setup_complete", "complete_button")
        st.toast("Event sent: setup_complete")

st.markdown("#### ⚠️ Stuck Signals")
cols2 = st.columns(4)

with cols2[0]:
    if st.button("❓ Click Help", use_container_width=True):
        send_event("help_click", "help_button")
        st.toast("Stuck signal: help_click")

with cols2[1]:
    if st.button("❌ Click Cancel", use_container_width=True):
        send_event("cancel_click", "cancel_button")
        st.toast("Stuck signal: cancel_click")

with cols2[2]:
    if st.button("⬅️ Go Back", use_container_width=True):
        send_event("back_click", "back_button")
        st.toast("Stuck signal: back_click")

with cols2[3]:
    if st.button("🔄 Repeated Click", use_container_width=True):
        for i in range(3):
            send_event("click", "same_button", {"attempt": i + 1})
        st.toast("Stuck signal: repeated clicks")

st.markdown("---")

# ── Event Log & Nudges ────────────────────────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("📋 Event Log")
    if st.session_state.event_log:
        log_html = "<br>".join(reversed(st.session_state.event_log[-20:]))
        st.markdown(f'<div class="event-log">{log_html}</div>', unsafe_allow_html=True)
    else:
        st.info("No events sent yet. Click the buttons above to simulate user actions.")

with right:
    st.subheader("💬 Received Nudges")
    # Poll for nudges from the database
    if st.button("🔄 Check for Nudges", use_container_width=True):
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            resp = httpx.get(
                f"http://localhost:{settings.FASTAPI_PORT}/api/v1/config/dashboard/nudges",
                headers=headers,
                params={"limit": 10},
            )
            if resp.status_code == 200:
                nudges = resp.json()
                user_nudges = [n for n in nudges if n.get("user_id") == st.session_state.demo_user_id]
                st.session_state.nudges_received = user_nudges
        except Exception as e:
            st.error(f"Error fetching nudges: {e}")

    if st.session_state.nudges_received:
        for nudge in st.session_state.nudges_received:
            nudge_type_icons = {"tooltip": "💡", "in_app_chat": "💬", "email_draft": "📧"}
            icon = nudge_type_icons.get(nudge.get("nudge_type"), "📢")
            st.markdown(f"""
            <div class="nudge-card">
                <strong>{icon} {nudge.get('nudge_type', 'nudge').replace('_', ' ').title()}</strong><br>
                <span>{nudge.get('content', '')}</span><br>
                <small>Stuck at: {nudge.get('stuck_point', 'N/A')} | {nudge.get('sent_at', '')[:19]}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No nudges yet. Send some stuck signals and check back!")
