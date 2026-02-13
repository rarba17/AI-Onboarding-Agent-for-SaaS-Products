"""
Onboarding Funnel — Visual representation of user drop-off at each onboarding step.
"""

import streamlit as st
import httpx
import plotly.graph_objects as go
import plotly.express as px
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Onboarding Funnel", page_icon="📊", layout="wide")
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# 📊 Onboarding Funnel")
st.markdown("Track where users drop off during their onboarding journey.")

headers = {"Authorization": f"Bearer {st.session_state.token}"}
base_url = f"http://localhost:{settings.FASTAPI_PORT}"

try:
    resp = httpx.get(f"{base_url}/api/v1/config/dashboard/funnel", headers=headers)
    funnel_data = resp.json()
except Exception:
    funnel_data = {"steps": []}

steps = funnel_data.get("steps", [])

if steps:
    col1, col2 = st.columns([2, 1])

    with col1:
        # Funnel chart
        fig = go.Figure(go.Funnel(
            y=[s["step"] for s in steps],
            x=[s["users"] for s in steps],
            textinfo="value+percent initial+percent previous",
            marker=dict(
                color=["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#43e97b"],
            ),
            connector={"line": {"color": "#e8e8e8", "dash": "dot", "width": 2}},
        ))
        fig.update_layout(
            title="User Progression Through Onboarding Steps",
            height=450,
            margin=dict(l=20, r=20, t=60, b=20),
            font=dict(family="Inter"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("📈 Step Details")
        for i, step in enumerate(steps):
            users = step.get("users", 0)
            prev_users = steps[i - 1].get("users", users) if i > 0 else users
            drop_rate = ((prev_users - users) / prev_users * 100) if prev_users > 0 and i > 0 else 0

            st.metric(
                label=step["step"],
                value=f"{users} users",
                delta=f"-{drop_rate:.0f}% drop" if drop_rate > 0 else "Entry point" if i == 0 else "No drop",
                delta_color="inverse",
            )

    # Bar chart comparison
    st.markdown("---")
    st.subheader("📉 Drop-off Analysis")
    fig_bar = px.bar(
        x=[s["step"] for s in steps],
        y=[s["users"] for s in steps],
        color=[s["users"] for s in steps],
        color_continuous_scale="Viridis",
        labels={"x": "Onboarding Step", "y": "Users", "color": "Users"},
    )
    fig_bar.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        font=dict(family="Inter"),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.info("""
    📊 **No funnel data yet!**

    To see the funnel:
    1. Go to **Configuration** → define your success baseline steps
    2. Go to **Demo Client** → simulate user events
    3. Come back here to see the funnel visualization
    """)
