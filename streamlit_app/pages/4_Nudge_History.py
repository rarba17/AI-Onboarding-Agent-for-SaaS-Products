"""
Nudge History — Log of all nudges sent, their type, and outcomes.
"""

import streamlit as st
import httpx
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Nudge History", page_icon="💬", layout="wide")
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# 💬 Nudge History")
st.markdown("View all AI-generated nudges and their outcomes.")

headers = {"Authorization": f"Bearer {st.session_state.token}"}
base_url = f"http://localhost:{settings.FASTAPI_PORT}"

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    filter_type = st.selectbox("Nudge Type", ["All", "tooltip", "in_app_chat", "email_draft"])
with col2:
    filter_status = st.selectbox("Status", ["All", "sent", "delivered", "clicked", "dismissed"])
with col3:
    limit = st.slider("Show", 10, 100, 50)

try:
    resp = httpx.get(
        f"{base_url}/api/v1/config/dashboard/nudges",
        headers=headers,
        params={"limit": limit},
    )
    nudges = resp.json() if resp.status_code == 200 else []
except Exception:
    nudges = []

# Apply filters
if filter_type != "All":
    nudges = [n for n in nudges if n.get("nudge_type") == filter_type]
if filter_status != "All":
    nudges = [n for n in nudges if n.get("status") == filter_status]

if nudges:
    # Summary
    type_counts = {}
    for n in nudges:
        t = n.get("nudge_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    cols = st.columns(len(type_counts) + 1)
    cols[0].metric("Total Nudges", len(nudges))
    for i, (t, count) in enumerate(type_counts.items()):
        icons = {"tooltip": "💡", "in_app_chat": "💬", "email_draft": "📧"}
        cols[i + 1].metric(f"{icons.get(t, '📢')} {t}", count)

    st.markdown("---")

    # Table
    df = pd.DataFrame(nudges)
    display_cols = ["sent_at", "user_id", "nudge_type", "content", "stuck_point", "status"]
    available = [c for c in display_cols if c in df.columns]

    if available:
        df_display = df[available].copy()
        if "sent_at" in df_display.columns:
            df_display["sent_at"] = pd.to_datetime(df_display["sent_at"]).dt.strftime("%m/%d %H:%M")
        if "content" in df_display.columns:
            df_display["content"] = df_display["content"].str[:100] + "..."

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "sent_at": st.column_config.TextColumn("Sent At", width="small"),
                "user_id": st.column_config.TextColumn("User", width="small"),
                "nudge_type": st.column_config.TextColumn("Type", width="small"),
                "content": st.column_config.TextColumn("Content", width="large"),
                "stuck_point": st.column_config.TextColumn("Stuck Point", width="medium"),
                "status": st.column_config.TextColumn("Status", width="small"),
            },
        )

    # Expandable details
    st.markdown("---")
    st.subheader("📝 Detailed View")
    for nudge in nudges[:10]:
        icons = {"tooltip": "💡", "in_app_chat": "💬", "email_draft": "📧"}
        icon = icons.get(nudge.get("nudge_type"), "📢")
        with st.expander(f"{icon} {nudge.get('stuck_point', 'N/A')} — {nudge.get('user_id', '?')[:20]}"):
            st.markdown(f"**Content:** {nudge.get('content', 'N/A')}")
            st.markdown(f"**Type:** {nudge.get('nudge_type')} | **Status:** {nudge.get('status')}")
            st.markdown(f"**Sent:** {nudge.get('sent_at', 'N/A')}")
            if nudge.get("diagnosis"):
                st.json(nudge["diagnosis"])
else:
    st.info("💬 No nudges sent yet. Use the **Demo Client** to trigger some events!")
