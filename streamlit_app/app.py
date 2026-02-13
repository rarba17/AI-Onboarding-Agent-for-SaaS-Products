"""
AI Onboarding Agent — Streamlit App
Main entry point with navigation and authentication.
"""

import streamlit as st
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared_config import settings

# ── Page Config ───────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Onboarding Agent",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global styling */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .main-header p {
        color: rgba(255,255,255,0.85);
        margin: 0.5rem 0 0 0;
        font-size: 1rem;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    .metric-card h3 {
        color: #667eea;
        font-size: 2rem;
        margin: 0;
        font-weight: 700;
    }
    .metric-card p {
        color: #4a5568;
        margin: 0.25rem 0 0 0;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-open { background: #fed7d7; color: #c53030; }
    .status-progress { background: #fefcbf; color: #b7791f; }
    .status-resolved { background: #c6f6d5; color: #276749; }
    .status-sent { background: #bee3f8; color: #2b6cb0; }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: rgba(255,255,255,0.8);
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Smooth transitions */
    .stButton button {
        transition: all 0.3s ease;
        border-radius: 8px;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
</style>
""", unsafe_allow_html=True)


# ── Auth State ────────────────────────────────────────────────────

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.company_id = None
    st.session_state.role = None
    st.session_state.email = None


# ── Login / Signup ────────────────────────────────────────────────

def show_auth():
    """Show login/signup form."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="main-header" style="text-align: center;">
            <h1>🧭 AI Onboarding Agent</h1>
            <p>Reduce churn. Activate users. Powered by AI.</p>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔑 Login", "🆕 Sign Up"])

        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="admin@company.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)

                if submitted and email and password:
                    import httpx
                    try:
                        resp = httpx.post(
                            f"http://localhost:{settings.FASTAPI_PORT}/api/v1/auth/login",
                            json={"email": email, "password": password},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.authenticated = True
                            st.session_state.token = data["access_token"]
                            st.session_state.company_id = data["company_id"]
                            st.session_state.role = data["role"]
                            st.session_state.email = email
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    except httpx.ConnectError:
                        st.error("⚠️ Cannot connect to backend. Make sure FastAPI is running.")

        with tab2:
            with st.form("signup_form"):
                name = st.text_input("Full Name", placeholder="Jane Doe")
                email = st.text_input("Email", placeholder="jane@startup.com", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password")
                submitted = st.form_submit_button("Create Account", use_container_width=True)

                if submitted and email and password:
                    import httpx
                    try:
                        resp = httpx.post(
                            f"http://localhost:{settings.FASTAPI_PORT}/api/v1/auth/signup",
                            json={"email": email, "password": password, "full_name": name},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.authenticated = True
                            st.session_state.token = data["access_token"]
                            st.session_state.company_id = data["company_id"]
                            st.session_state.role = data["role"]
                            st.session_state.email = email
                            st.success("✅ Account created! Redirecting...")
                            st.rerun()
                        else:
                            st.error(f"Signup failed: {resp.json().get('detail', 'Unknown error')}")
                    except httpx.ConnectError:
                        st.error("⚠️ Cannot connect to backend. Make sure FastAPI is running.")


# ── Main Dashboard Home ──────────────────────────────────────────

def show_home():
    """Show the main dashboard home page."""
    import httpx

    st.markdown("""
    <div class="main-header">
        <h1>🧭 AI Onboarding Agent</h1>
        <p>Your intelligent onboarding co-pilot — monitoring, diagnosing, and coaching in real-time.</p>
    </div>
    """, unsafe_allow_html=True)

    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    base_url = f"http://localhost:{settings.FASTAPI_PORT}"

    # Fetch dashboard data
    try:
        funnel = httpx.get(f"{base_url}/api/v1/config/dashboard/funnel", headers=headers).json()
        sessions = httpx.get(f"{base_url}/api/v1/config/dashboard/sessions", headers=headers).json()
        nudges = httpx.get(f"{base_url}/api/v1/config/dashboard/nudges", headers=headers).json()
        escalations = httpx.get(f"{base_url}/api/v1/config/dashboard/escalations", headers=headers).json()
    except Exception:
        funnel = {"steps": []}
        sessions = []
        nudges = []
        escalations = []

    # Metric cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(sessions)}</h3>
            <p>Active Sessions</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(nudges)}</h3>
            <p>Nudges Sent</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        open_escalations = len([e for e in escalations if e.get("status") == "open"])
        st.markdown(f"""
        <div class="metric-card">
            <h3>{open_escalations}</h3>
            <p>Open Escalations</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        funnel_steps = funnel.get("steps", [])
        activation_rate = "N/A"
        if len(funnel_steps) >= 2 and funnel_steps[0].get("users", 0) > 0:
            rate = (funnel_steps[-1].get("users", 0) / funnel_steps[0]["users"]) * 100
            activation_rate = f"{rate:.0f}%"
        st.markdown(f"""
        <div class="metric-card">
            <h3>{activation_rate}</h3>
            <p>Activation Rate</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Quick funnel preview
    if funnel_steps:
        st.subheader("📊 Onboarding Funnel")
        import plotly.graph_objects as go

        fig = go.Figure(go.Funnel(
            y=[step.get("step", "?") for step in funnel_steps],
            x=[step.get("users", 0) for step in funnel_steps],
            textinfo="value+percent initial",
            marker=dict(
                color=["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe"],
            ),
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📊 No funnel data yet. Configure a baseline and start sending events!")

    # Sidebar user info
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"**Logged in as:** {st.session_state.email}")
        st.markdown(f"**Role:** {st.session_state.role}")
        if st.button("🚪 Logout", use_container_width=True):
            for key in ["authenticated", "token", "company_id", "role", "email"]:
                st.session_state[key] = None
            st.session_state.authenticated = False
            st.rerun()


# ── Router ────────────────────────────────────────────────────────

if st.session_state.authenticated:
    show_home()
else:
    show_auth()
