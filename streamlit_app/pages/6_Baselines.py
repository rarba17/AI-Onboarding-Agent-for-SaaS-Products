"""
Baselines — Define and edit success paths for onboarding.
"""

import streamlit as st
import httpx
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Baselines", page_icon="🎯", layout="wide")
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .step-card {
        background: white;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .step-number {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
    }
</style>""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# 🎯 Success Baselines")
st.markdown("Define the ideal onboarding path. The AI uses this to detect when users deviate.")

headers = {"Authorization": f"Bearer {st.session_state.token}"}
base_url = f"http://localhost:{settings.FASTAPI_PORT}"

# Fetch baselines
try:
    resp = httpx.get(f"{base_url}/api/v1/config/baselines", headers=headers)
    baselines = resp.json() if resp.status_code == 200 else []
except Exception:
    baselines = []

# ── Existing Baselines ────────────────────────────────────────────

if baselines:
    for baseline in baselines:
        status = "🟢 Active" if baseline.get("is_active") else "⚪ Inactive"
        with st.expander(f"{status} {baseline.get('name', 'Unnamed')} — {len(baseline.get('event_sequence', []))} steps"):
            steps = baseline.get("event_sequence", [])

            # Show visual path
            path_parts = []
            for step in steps:
                label = step.get("label", step.get("event_type", "?"))
                path_parts.append(label)
            st.markdown(" → ".join([f"**{p}**" for p in path_parts]))

            # Editable steps
            st.markdown("#### Edit Steps")
            edited_steps = []
            for i, step in enumerate(steps):
                cols = st.columns([1, 2, 2])
                with cols[0]:
                    st.markdown(f"**Step {i + 1}**")
                with cols[1]:
                    event_type = st.text_input(
                        "Event Type",
                        value=step.get("event_type", ""),
                        key=f"et_{baseline['baseline_id']}_{i}",
                    )
                with cols[2]:
                    label = st.text_input(
                        "Label",
                        value=step.get("label", ""),
                        key=f"lb_{baseline['baseline_id']}_{i}",
                    )
                edited_steps.append({
                    "event_type": event_type,
                    "label": label,
                    "order": i,
                })

            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"💾 Save Changes", key=f"save_{baseline['baseline_id']}", use_container_width=True, type="primary"):
                    try:
                        resp = httpx.put(
                            f"{base_url}/api/v1/config/baselines/{baseline['baseline_id']}",
                            headers=headers,
                            json={
                                "name": baseline["name"],
                                "event_sequence": edited_steps,
                                "is_active": baseline.get("is_active", True),
                            },
                        )
                        if resp.status_code == 200:
                            st.success("✅ Baseline updated!")
                            st.rerun()
                        else:
                            st.error(f"Failed: {resp.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
            with col2:
                if st.button(f"🗑️ Delete", key=f"del_{baseline['baseline_id']}", use_container_width=True):
                    try:
                        resp = httpx.delete(
                            f"{base_url}/api/v1/config/baselines/{baseline['baseline_id']}",
                            headers=headers,
                        )
                        st.success("Deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

st.markdown("---")

# ── Create New Baseline ───────────────────────────────────────────

st.subheader("➕ Create New Baseline")

baseline_name = st.text_input("Baseline Name", placeholder="e.g., Standard Onboarding")

st.markdown("**Define Steps:**")
num_steps = st.number_input("Number of Steps", min_value=2, max_value=10, value=3)

new_steps = []
for i in range(num_steps):
    cols = st.columns([1, 2, 2])
    with cols[0]:
        st.markdown(f"**Step {i + 1}**")
    with cols[1]:
        et = st.text_input("Event Type", placeholder="e.g., signup", key=f"new_et_{i}")
    with cols[2]:
        lb = st.text_input("Label", placeholder="e.g., Sign Up", key=f"new_lb_{i}")
    new_steps.append({"event_type": et, "label": lb, "order": i})

if st.button("🎯 Create Baseline", type="primary", use_container_width=True):
    if not baseline_name:
        st.error("Please enter a baseline name")
    elif not all(s["event_type"] for s in new_steps):
        st.error("All steps must have an event type")
    else:
        try:
            resp = httpx.post(
                f"{base_url}/api/v1/config/baselines",
                headers=headers,
                json={
                    "name": baseline_name,
                    "event_sequence": new_steps,
                    "is_active": True,
                },
            )
            if resp.status_code == 200:
                st.success("✅ Baseline created!")
                st.rerun()
            else:
                st.error(f"Failed: {resp.text}")
        except Exception as e:
            st.error(f"Error: {e}")
