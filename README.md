# 🧭 AI Onboarding Agent

> Reduce B2B SaaS user churn by 50% with AI-powered, personalized onboarding guidance.

An intelligent multi-agent system that monitors new user behavior, diagnoses stuck points in real-time, and delivers personalized nudges to guide users to their "Aha!" moment.

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Streamlit App   │────▶│  FastAPI API  │────▶│   Redis Stream      │
│  (Demo + Admin)  │◀────│  (Gateway)   │     │   (Event Queue)     │
└─────────────────┘     └──────┬───────┘     └──────────┬──────────┘
                               │                         │
                        ┌──────┴───────┐     ┌──────────▼──────────┐
                        │  PostgreSQL  │◀────│   LangGraph Worker   │
                        │  (Docker)    │     │   (AI Multi-Agent)   │
                        └──────────────┘     └─────────────────────┘
```

**Tech Stack:** FastAPI • LangGraph • OpenAI GPT-4o • PostgreSQL (Docker) • Redis • Streamlit

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- OpenAI API key

### 1. Clone & Setup

```bash
cd saas

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r backend/requirements.txt
pip install -r ai_core/requirements.txt
pip install -r streamlit_app/requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — only REQUIRED changes:
#   OPENAI_API_KEY=sk-your-key-here
#   JWT_SECRET_KEY=any-random-string
# Everything else works out of the box with Docker defaults!
```

### 3. Start Docker Services (PostgreSQL + Redis)

```bash
docker compose up -d
# This starts Postgres (port 5432) and Redis (port 6379)
# The database schema is auto-created on first boot via init.sql
```

### 4. Run the Application

```bash
# Terminal 1: FastAPI server
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2: AI Worker (processes events)
python -m ai_core.worker

# Terminal 3: Streamlit app
streamlit run streamlit_app/app.py
```

### 5. Open the App

Visit **http://localhost:8501** → Sign up → Start exploring!

## 📱 Features

| Page | Description |
|------|-------------|
| 🏠 **Home** | Dashboard with key metrics and funnel overview |
| 🎮 **Demo Client** | Simulate user onboarding journey and see AI nudges |
| 📊 **Onboarding Funnel** | Visual drop-off analysis at each step |
| 👁️ **Live Sessions** | Monitor active users in real-time |
| 💬 **Nudge History** | Filterable log of all AI-generated nudges |
| ⚙️ **Configuration** | Tone/voice, escalation thresholds, API keys |
| 🎯 **Baselines** | Define success paths for onboarding |
| 🚨 **Escalation Queue** | CSM case management for stuck users |

## 🤖 AI Multi-Agent System

```
Diagnosis Agent → Decision Router → Coach Agent → Action Taker → Escalation (conditional)
```

1. **Diagnosis Agent** — Analyzes session events against success baseline
2. **Decision Router** — Only proceeds if confidence > 0.6
3. **Coach Agent** — Generates personalized nudge content
4. **Action Taker** — Delivers nudge and tracks counter
5. **Escalation Agent** — Alerts CSMs when nudges aren't working

## 📁 Project Structure

```
saas/
├── backend/          # FastAPI API server
│   └── app/
│       ├── main.py          # App entry point
│       ├── routes/          # API endpoints
│       ├── models/          # Pydantic schemas
│       ├── services/        # Auth & business logic
│       ├── db/
│       │   ├── supabase_client.py  # PostgreSQL client (psycopg2)
│       │   ├── redis_client.py     # Redis client
│       │   └── init.sql            # Schema (auto-executed by Docker)
│       └── ws/              # WebSocket manager
├── ai_core/          # LangGraph multi-agent system
│   ├── agents/              # Diagnosis, Coach, Action, Escalation
│   ├── workflow.py          # StateGraph definition
│   └── worker.py            # Redis Stream consumer
├── streamlit_app/    # Streamlit UI
│   ├── app.py               # Main entry
│   └── pages/               # 7 sub-pages
├── docker-compose.yml       # PostgreSQL + Redis
├── shared_config.py
└── .env.example
```

## 🔑 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/events` | Ingest batched events (SDK) |
| WS | `/ws/{user_id}` | Real-time nudge delivery |
| POST | `/api/v1/auth/signup` | Create account + company |
| POST | `/api/v1/auth/login` | Get JWT token |
| GET | `/api/v1/config/company` | Get company settings |
| PATCH | `/api/v1/config/company` | Update settings |
| GET/POST | `/api/v1/config/baselines` | CRUD baselines |
| GET | `/api/v1/config/dashboard/*` | Dashboard data |
| GET | `/docs` | Auto-generated API docs |

## 🐳 Docker Services

| Service | Port | Credentials |
|---------|------|-------------|
| PostgreSQL | 5432 | `onboarding` / `onboarding_secret` |
| Redis | 6379 | No auth |
