"""
Escalation Queue — CSMs manage escalated user cases.
"""

import streamlit as st
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Escalation Queue", page_icon="🚨", layout="wide")
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .esc-card {
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border-left: 4px solid;
    }
    .esc-open { background: #fff5f5; border-color: #fc8181; }
    .esc-progress { background: #fffff0; border-color: #f6e05e; }
    .esc-resolved { background: #f0fff4; border-color: #68d391; }
</style>""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# 🚨 Escalation Queue")
st.markdown("Manage users who need human assistance — the AI couldn't resolve their issues.")

headers = {"Authorization": f"Bearer {st.session_state.token}"}
base_url = f"http://localhost:{settings.FASTAPI_PORT}"

# Filter
status_filter = st.selectbox("Filter by Status", ["all", "open", "in_progress", "resolved", "dismissed"])

try:
    resp = httpx.get(f"{base_url}/api/v1/config/dashboard/escalations", headers=headers)
    escalations = resp.json() if resp.status_code == 200 else []
except Exception:
    escalations = []

if status_filter != "all":
    escalations = [e for e in escalations if e.get("status") == status_filter]

# Summary
if escalations:
    col1, col2, col3, col4 = st.columns(4)
    all_esc = [e for e in escalations]
    col1.metric("🔴 Open", sum(1 for e in all_esc if e.get("status") == "open"))
    col2.metric("🟡 In Progress", sum(1 for e in all_esc if e.get("status") == "in_progress"))
    col3.metric("🟢 Resolved", sum(1 for e in all_esc if e.get("status") == "resolved"))
    col4.metric("⚪ Dismissed", sum(1 for e in all_esc if e.get("status") == "dismissed"))

    st.markdown("---")

    for esc in escalations:
        status = esc.get("status", "open")
        css_class = {
            "open": "esc-open",
            "in_progress": "esc-progress",
            "resolved": "esc-resolved",
        }.get(status, "esc-open")

        status_icons = {
            "open": "🔴",
            "in_progress": "🟡",
            "resolved": "🟢",
            "dismissed": "⚪",
        }

        with st.container():
            st.markdown(f"""
            <div class="esc-card {css_class}">
                <strong>{status_icons.get(status, '❓')} {esc.get('stuck_point', 'Unknown Issue')}</strong><br>
                <small>User: {esc.get('user_id', 'N/A')} | Created: {str(esc.get('created_at', ''))[:16]}</small>
            </div>
            """, unsafe_allow_html=True)

            with st.expander(f"Details — {esc.get('user_id', '?')[:20]}"):
                st.markdown(f"**Inferred Reason:** {esc.get('inferred_reason', 'N/A')}")
                st.markdown(f"**Status:** {status}")

                # Nudge log
                nudge_log = esc.get("nudge_log", [])
                if nudge_log:
                    st.markdown("**Previous Nudges:**")
                    for nudge in nudge_log:
                        st.markdown(f"- [{nudge.get('nudge_type', '?')}] {nudge.get('content', '?')[:80]}...")

                # Actions
                cols = st.columns(3)
                with cols[0]:
                    if status == "open" and st.button(
                        "🟡 Take On", key=f"take_{esc['id']}", use_container_width=True
                    ):
                        try:
                            httpx.patch(
                                f"{base_url}/api/v1/config/dashboard/escalations/{esc['id']}",
                                headers=headers,
                                params={"status": "in_progress"},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                with cols[1]:
                    if status in ("open", "in_progress") and st.button(
                        "🟢 Resolve", key=f"resolve_{esc['id']}", use_container_width=True
                    ):
                        try:
                            httpx.patch(
                                f"{base_url}/api/v1/config/dashboard/escalations/{esc['id']}",
                                headers=headers,
                                params={"status": "resolved"},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                with cols[2]:
                    if status in ("open", "in_progress") and st.button(
                        "⚪ Dismiss", key=f"dismiss_{esc['id']}", use_container_width=True
                    ):
                        try:
                            httpx.patch(
                                f"{base_url}/api/v1/config/dashboard/escalations/{esc['id']}",
                                headers=headers,
                                params={"status": "dismissed"},
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
else:
    st.info("🎉 No escalations! Your AI onboarding agent is handling everything.")
