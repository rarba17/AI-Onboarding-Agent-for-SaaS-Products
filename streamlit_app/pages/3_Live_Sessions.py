"""
Live Sessions — View currently active users and their last known action.
"""

import streamlit as st
import httpx
import pandas as pd
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings

st.set_page_config(page_title="Live Sessions", page_icon="👁️", layout="wide")
st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .active-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #48bb78; margin-right: 8px; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>""", unsafe_allow_html=True)

if not st.session_state.get("authenticated"):
    st.warning("🔒 Please login from the main page first.")
    st.stop()

st.markdown("# 👁️ Live Sessions")
st.markdown("Monitor currently active users in real-time.")

# Auto-refresh toggle
auto_refresh = st.toggle("Auto-refresh (every 10s)", value=False)
if auto_refresh:
    st.markdown('<meta http-equiv="refresh" content="10">', unsafe_allow_html=True)

headers = {"Authorization": f"Bearer {st.session_state.token}"}
base_url = f"http://localhost:{settings.FASTAPI_PORT}"

try:
    resp = httpx.get(f"{base_url}/api/v1/config/dashboard/sessions", headers=headers)
    sessions = resp.json() if resp.status_code == 200 else []
except Exception:
    sessions = []

if sessions:
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Users", len(sessions))
    with col2:
        now = datetime.now(timezone.utc)
        recent = sum(1 for s in sessions if s.get("last_seen_time"))
        st.metric("Seen Last 5 min", recent)
    with col3:
        unique_users = len(set(s.get("user_id", "") for s in sessions))
        st.metric("Unique Users", unique_users)

    st.markdown("---")

    # Sessions table
    df = pd.DataFrame(sessions)
    display_cols = ["user_id", "session_id", "start_time", "last_seen_time", "is_active"]
    available_cols = [c for c in display_cols if c in df.columns]

    if available_cols:
        df_display = df[available_cols].copy()
        if "start_time" in df_display.columns:
            df_display["start_time"] = pd.to_datetime(df_display["start_time"]).dt.strftime("%H:%M:%S")
        if "last_seen_time" in df_display.columns:
            df_display["last_seen_time"] = pd.to_datetime(df_display["last_seen_time"]).dt.strftime("%H:%M:%S")
        if "is_active" in df_display.columns:
            df_display["is_active"] = df_display["is_active"].map({True: "🟢 Active", False: "🔴 Inactive"})

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "user_id": st.column_config.TextColumn("User ID", width="medium"),
                "session_id": st.column_config.TextColumn("Session", width="medium"),
                "start_time": st.column_config.TextColumn("Started", width="small"),
                "last_seen_time": st.column_config.TextColumn("Last Seen", width="small"),
                "is_active": st.column_config.TextColumn("Status", width="small"),
            },
        )
else:
    st.info("👁️ No active sessions. Go to the **Demo Client** to simulate user activity.")
