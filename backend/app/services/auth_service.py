"""
Authentication and authorization utilities.
Handles JWT tokens and API key validation.
"""

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import hashlib
import secrets
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared_config import settings
from backend.app.db.supabase_client import get_db

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, hashed_key)."""
    raw_key = f"oba_{secrets.token_urlsafe(32)}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> dict:
    """Dependency: validate JWT and return admin user info."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_access_token(credentials.credentials)
    return {
        "user_id": payload.get("sub"),
        "company_id": payload.get("company_id"),
        "role": payload.get("role"),
        "email": payload.get("email"),
    }


async def validate_api_key(
    api_key: str = Security(api_key_header),
) -> dict:
    """Dependency: validate API key and return company info."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    hashed = hash_api_key(api_key)
    db = get_db()
    result = db.table("api_keys").select("*").eq("key_hash", hashed).eq("is_active", True).execute()

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    key_data = result.data[0]
    company_id = key_data["company_id"]

    # Fetch company name separately
    company_result = db.table("companies").select("name").eq("id", company_id).execute()
    company_name = company_result.data[0]["name"] if company_result.data else ""

    return {
        "company_id": company_id,
        "company_name": company_name,
    }
