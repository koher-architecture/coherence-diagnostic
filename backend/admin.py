"""
Admin Module for Coherence Diagnostic

This module handles:
- Admin authentication
- User listing and management
- Waitlist management
- Usage statistics

Only loaded when ENABLE_AUTH=1 in config.
"""

from datetime import date
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ADMIN_PASSWORD, MAX_ANALYSES_PER_USER, MAX_NEW_USERS_PER_DAY

# Import database functions from auth module
from backend.auth import get_db_connection


# =============================================================================
# Admin Authentication
# =============================================================================

def verify_admin(password: Optional[str]) -> bool:
    """Check if password matches admin password."""
    return password == ADMIN_PASSWORD


# =============================================================================
# Data Access Functions
# =============================================================================

def get_all_users() -> list:
    """Get all users (for admin)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, email, verified, created_at, usage_count
        FROM users
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "verified": bool(row[3]),
            "created_at": row[4],
            "usage_count": row[5],
            "remaining_analyses": MAX_ANALYSES_PER_USER - row[5]
        }
        for row in rows
    ]


def get_waitlist() -> list:
    """Get all waitlist entries (for admin)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, email, created_at
        FROM waitlist
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "created_at": row[3]
        }
        for row in rows
    ]


def get_daily_stats() -> dict:
    """Get today's stats."""
    conn = get_db_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()
    cursor.execute("SELECT users_created FROM daily_stats WHERE date = ?", (today,))
    row = cursor.fetchone()

    conn.close()

    users_today = row[0] if row else 0
    return {
        "date": today,
        "users_created_today": users_today,
        "remaining_slots": MAX_NEW_USERS_PER_DAY - users_today
    }


# =============================================================================
# Request Models
# =============================================================================

class AdminLoginRequest(BaseModel):
    password: str = Field(..., description="Admin password")


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/admin", tags=["Admin"])

ADMIN_PAGE_PATH = Path(__file__).parent.parent / "frontend" / "admin.html"


@router.post("/login")
async def admin_login(request: AdminLoginRequest):
    """Verify admin password."""
    if not verify_admin(request.password):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return {"success": True, "message": "Admin authenticated"}


@router.get("/users")
async def list_users(admin_password: str):
    """List all users (admin only)."""
    if not verify_admin(admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    users = get_all_users()
    return {"users": users, "total": len(users)}


@router.get("/waitlist")
async def list_waitlist(admin_password: str):
    """List waitlist entries (admin only)."""
    if not verify_admin(admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    entries = get_waitlist()
    return {"waitlist": entries, "total": len(entries)}


@router.get("/stats")
async def admin_stats(admin_password: str):
    """Get usage statistics (admin only)."""
    if not verify_admin(admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    stats = get_daily_stats()
    users = get_all_users()
    waitlist = get_waitlist()

    total_usage = sum(u["usage_count"] for u in users)
    active_users = sum(1 for u in users if u["usage_count"] > 0)
    verified_users = sum(1 for u in users if u["verified"])
    unverified_users = sum(1 for u in users if not u["verified"])
    exhausted_users = sum(1 for u in users if u["remaining_analyses"] <= 0)

    return {
        "daily": stats,
        "totals": {
            "total_users": len(users),
            "verified_users": verified_users,
            "unverified_users": unverified_users,
            "active_users": active_users,
            "exhausted_users": exhausted_users,
            "total_analyses": total_usage,
            "waitlist_count": len(waitlist),
            "max_analyses_per_user": MAX_ANALYSES_PER_USER,
            "max_new_users_per_day": MAX_NEW_USERS_PER_DAY
        }
    }


@router.get("", include_in_schema=False)
async def serve_admin():
    """Serve the admin page."""
    if ADMIN_PAGE_PATH.exists():
        return FileResponse(ADMIN_PAGE_PATH)
    return HTMLResponse(content="<h1>Admin page not found</h1>", status_code=404)
