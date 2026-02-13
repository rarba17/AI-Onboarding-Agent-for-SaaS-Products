"""
FastAPI main application entry point.
Registers all routes, middleware, and WebSocket endpoints.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared_config import settings
from backend.app.routes import events, auth, config
from backend.app.ws.manager import ws_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── App Setup ─────────────────────────────────────────────────────

app = FastAPI(
    title="AI Onboarding Agent API",
    description="Multi-agent AI system for reducing B2B SaaS user churn through personalized onboarding.",
    version="1.0.0-mvp",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routes ───────────────────────────────────────────────

app.include_router(events.router)
app.include_router(auth.router)
app.include_router(config.router)


# ── WebSocket Endpoint ────────────────────────────────────────────

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket connection for real-time nudge delivery.
    The SDK connects here to receive nudges from the AI agents.
    """
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user={user_id}: {e}")
        ws_manager.disconnect(user_id)


# ── Health Check ──────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0-mvp"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI Onboarding Agent API",
        "version": "1.0.0-mvp",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=settings.FASTAPI_PORT, reload=True)
