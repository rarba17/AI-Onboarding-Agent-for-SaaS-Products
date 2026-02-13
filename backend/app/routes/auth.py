"""
Authentication routes.
Handles admin signup, login, and API key management.
"""

from fastapi import APIRouter, HTTPException, Depends
from backend.app.models.config import AdminUserCreate, AdminUserLogin, TokenResponse
from backend.app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_admin,
    generate_api_key,
)
from backend.app.db.supabase_client import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(user: AdminUserCreate):
    """
    Register a new admin user and company.
    Creates the company, admin user, and a default API key.
    """
    db = get_db()

    # Check if email exists
    existing = db.table("admin_users").select("id").eq("email", user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        # Create company
        company_result = db.table("companies").insert({
            "name": f"{user.full_name or user.email}'s Company",
        }).execute()
        company_id = company_result.data[0]["id"]

        # Create admin user
        admin_result = db.table("admin_users").insert({
            "company_id": company_id,
            "email": user.email,
            "password_hash": hash_password(user.password),
            "full_name": user.full_name,
            "role": user.role,
        }).execute()
        admin_id = admin_result.data[0]["id"]

        # Create default API key
        raw_key, hashed_key = generate_api_key()
        db.table("api_keys").insert({
            "company_id": company_id,
            "key_hash": hashed_key,
            "label": "default",
        }).execute()

        # Create default baseline
        db.table("baselines").insert({
            "company_id": company_id,
            "name": "Default Baseline",
            "event_sequence": [
                {"event_type": "signup", "label": "Sign Up", "order": 0},
                {"event_type": "create_project", "label": "Create First Project", "order": 1},
                {"event_type": "invite_team", "label": "Invite Team Member", "order": 2},
            ],
        }).execute()

        # Generate JWT
        token = create_access_token({
            "sub": admin_id,
            "company_id": company_id,
            "role": user.role,
            "email": user.email,
        })

        logger.info(f"New signup: {user.email} | Company: {company_id} | API Key: {raw_key[:12]}...")

        return TokenResponse(
            access_token=token,
            company_id=company_id,
            role=user.role,
        )

    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@router.post("/login", response_model=TokenResponse)
async def login(credentials: AdminUserLogin):
    """Login and receive a JWT token."""
    db = get_db()

    result = db.table("admin_users").select("*").eq("email", credentials.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = result.data[0]
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "sub": user["id"],
        "company_id": user["company_id"],
        "role": user["role"],
        "email": user["email"],
    })

    return TokenResponse(
        access_token=token,
        company_id=user["company_id"],
        role=user["role"],
    )


@router.get("/api-keys")
async def list_api_keys(admin: dict = Depends(get_current_admin)):
    """List API keys for the current company (shows only masked keys)."""
    db = get_db()
    result = db.table("api_keys").select("id, label, is_active, created_at").eq(
        "company_id", admin["company_id"]
    ).execute()
    return result.data


@router.post("/api-keys")
async def create_api_key(
    label: str = "default",
    admin: dict = Depends(get_current_admin),
):
    """Generate a new API key for the company."""
    db = get_db()
    raw_key, hashed_key = generate_api_key()

    db.table("api_keys").insert({
        "company_id": admin["company_id"],
        "key_hash": hashed_key,
        "label": label,
    }).execute()

    return {"api_key": raw_key, "label": label, "message": "Save this key — it won't be shown again."}
