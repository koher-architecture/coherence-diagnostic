"""
Authentication Module for Coherence Diagnostic

This module handles:
- Email verification flow
- Session cookies
- User registration and limits
- Database management for users

Only loaded when ENABLE_AUTH=1 in config.
"""

import secrets
import smtplib
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    SESSION_SECRET, ADMIN_PASSWORD, BASE_URL,
    MAX_ANALYSES_PER_USER, MAX_NEW_USERS_PER_DAY,
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME,
    DB_PATH
)


# =============================================================================
# Session Management
# =============================================================================

serializer = URLSafeTimedSerializer(SESSION_SECRET)
COOKIE_NAME = "koher_session"


def set_session_cookie(response: Response, email: str):
    """Sign email into a session cookie."""
    token = serializer.dumps(email)
    is_secure = BASE_URL.startswith("https")
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )


def get_session_email(request: Request) -> Optional[str]:
    """Extract email from session cookie. Returns None if invalid."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        email = serializer.loads(token)
        return email
    except (BadSignature, SignatureExpired):
        return None


# =============================================================================
# Database Management
# =============================================================================

def init_database():
    """Initialise SQLite database for user management."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Check if old password-based users table exists
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    row = cursor.fetchone()

    if row and "password TEXT PRIMARY KEY" in (row[0] or ""):
        cursor.execute("DROP TABLE users")
        print("Migrated: dropped old password-based users table")

    # Users table (email-based)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            verified INTEGER DEFAULT 0,
            verification_token TEXT,
            token_expires_at TEXT,
            created_at TEXT NOT NULL,
            usage_count INTEGER DEFAULT 0
        )
    """)

    # Daily stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            users_created INTEGER DEFAULT 0
        )
    """)

    # Waitlist table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(str(DB_PATH))


# =============================================================================
# Email Sending
# =============================================================================

def build_verification_email(name: str, verify_url: str) -> tuple[str, str]:
    """Build HTML and plain text versions of the verification email."""
    plain_text = f"""Hi {name},

Click the link below to verify your email and access the Coherence Diagnostic:

{verify_url}

This link expires in 1 hour.

— Koher
koher.app"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Georgia, 'Source Serif 4', serif; font-size: 16px; line-height: 1.7; color: #1a2332; max-width: 520px; margin: 0 auto; padding: 40px 20px;">
    <p style="margin-bottom: 20px;">Hi {name},</p>
    <p style="margin-bottom: 24px;">Click the button below to verify your email and access the Coherence Diagnostic.</p>
    <p style="margin-bottom: 32px;">
        <a href="{verify_url}" style="display: inline-block; padding: 14px 28px; background: #3b82a0; color: white; text-decoration: none; border-radius: 6px; font-family: 'IBM Plex Sans', sans-serif; font-size: 15px; font-weight: 500;">Verify Email</a>
    </p>
    <p style="font-size: 14px; color: #7a8fa6; margin-bottom: 8px;">Or copy this link:</p>
    <p style="font-size: 13px; color: #7a8fa6; word-break: break-all; margin-bottom: 32px;">{verify_url}</p>
    <p style="font-size: 14px; color: #7a8fa6;">This link expires in 1 hour.</p>
    <hr style="border: none; border-top: 1px solid #d1dce6; margin: 32px 0;">
    <p style="font-size: 13px; color: #7a8fa6;">Koher &mdash; <a href="https://koher.app" style="color: #3b82a0; text-decoration: none;">koher.app</a></p>
</body>
</html>"""

    return html, plain_text


def send_verification_email(name: str, email: str, token: str):
    """Send verification email via SMTP. Always prints URL to console."""
    verify_url = f"{BASE_URL}/auth/verify/{token}"
    html_body, plain_body = build_verification_email(name, verify_url)

    # Always print to console
    print(f"\n{'='*60}")
    print(f"VERIFICATION EMAIL")
    print(f"To: {email}")
    print(f"Verify URL: {verify_url}")
    print(f"{'='*60}\n")

    if not SMTP_HOST or not SMTP_USERNAME:
        return

    from_address = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"

    msg = MIMEMultipart("alternative")
    msg["From"] = from_address
    msg["To"] = email
    msg["Subject"] = "Verify your email — Coherence Diagnostic"

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, email, msg.as_string())
        print(f"Verification email sent to {email}")
    except Exception as e:
        print(f"Failed to send verification email to {email}: {e}")


# =============================================================================
# User Management Functions
# =============================================================================

def register_user(name: str, email: str) -> dict:
    """Register a new user or resend verification for existing user."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, email, verified FROM users WHERE email = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        user_id, existing_name, existing_email, verified = existing
        token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(hours=1)).isoformat()

        cursor.execute(
            "UPDATE users SET verification_token = ?, token_expires_at = ?, name = ? WHERE id = ?",
            (token, expires, name, user_id)
        )
        conn.commit()
        conn.close()

        send_verification_email(name, email, token)

        if verified:
            return {"status": "existing_verified", "message": "Verification link sent"}
        else:
            return {"status": "existing_unverified", "message": "Verification link resent"}

    # New user — check daily cap
    today = date.today().isoformat()
    cursor.execute("SELECT users_created FROM daily_stats WHERE date = ?", (today,))
    row = cursor.fetchone()
    users_today = row[0] if row else 0

    if users_today >= MAX_NEW_USERS_PER_DAY:
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO waitlist (name, email, created_at) VALUES (?, ?, ?)",
            (name, email, now)
        )
        conn.commit()
        conn.close()
        return {"status": "waitlisted", "message": "Daily signup limit reached"}

    # Create new user
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=1)).isoformat()
    now = datetime.now().isoformat()

    cursor.execute(
        """INSERT INTO users (name, email, verified, verification_token, token_expires_at, created_at, usage_count)
           VALUES (?, ?, 0, ?, ?, ?, 0)""",
        (name, email, token, expires, now)
    )

    cursor.execute("""
        INSERT INTO daily_stats (date, users_created) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET users_created = users_created + 1
    """, (today,))

    conn.commit()
    conn.close()

    send_verification_email(name, email, token)

    return {"status": "created", "message": "Verification link sent"}


def verify_token(token: str) -> Optional[dict]:
    """Verify a token and mark user as verified."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, email, verified, token_expires_at FROM users WHERE verification_token = ?",
        (token,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    user_id, name, email, verified, expires_at = row

    if expires_at:
        expires = datetime.fromisoformat(expires_at)
        if datetime.now() > expires:
            conn.close()
            return {"expired": True, "email": email}

    cursor.execute(
        "UPDATE users SET verified = 1, verification_token = NULL, token_expires_at = NULL WHERE id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()

    return {"id": user_id, "name": name, "email": email, "verified": True}


def get_authenticated_user(request: Request) -> Optional[dict]:
    """Get authenticated user from session cookie."""
    email = get_session_email(request)
    if not email:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, verified, usage_count FROM users WHERE email = ? AND verified = 1",
        (email,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "verified": row[3],
        "usage_count": row[4],
        "remaining_analyses": MAX_ANALYSES_PER_USER - row[4],
        "limit_reached": row[4] >= MAX_ANALYSES_PER_USER,
    }


def require_auth(request: Request) -> dict:
    """FastAPI dependency: require authenticated user or raise 401."""
    user = get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def increment_usage(email: str) -> int:
    """Increment usage count for a user. Returns new remaining count."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET usage_count = usage_count + 1 WHERE email = ?",
        (email,)
    )

    cursor.execute("SELECT usage_count FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()

    conn.commit()
    conn.close()

    return MAX_ANALYSES_PER_USER - row[0] if row else 0


# =============================================================================
# Verification Page HTML
# =============================================================================

def _verification_page(title: str, message: str) -> str:
    """Build a simple verification status HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Coherence Diagnostic</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Sans:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Source Serif 4', serif;
            background: #1a2332;
            color: #e8edf3;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #232d3f;
            border: 1px solid #2d3a4f;
            border-radius: 8px;
            padding: 48px;
            max-width: 440px;
            text-align: center;
        }}
        h1 {{
            font-family: 'Fraunces', serif;
            font-size: 24px;
            margin-bottom: 16px;
        }}
        p {{
            color: #7a8fa6;
            line-height: 1.7;
            margin-bottom: 24px;
        }}
        a {{
            display: inline-block;
            padding: 12px 28px;
            background: #3b82a0;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 15px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
        <a href="/">Back to Coherence Diagnostic</a>
    </div>
</body>
</html>"""


# =============================================================================
# Request Models
# =============================================================================

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's name")
    email: str = Field(..., min_length=5, max_length=200, description="User's email address")


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def auth_register(request: RegisterRequest):
    """Register a new user or resend verification link."""
    result = register_user(request.name, request.email)
    return result


@router.get("/verify/{token}")
async def auth_verify(token: str):
    """Verify email via magic link token."""
    result = verify_token(token)

    if not result:
        return HTMLResponse(
            content=_verification_page("Invalid Link", "This verification link is not valid. Please request a new one."),
            status_code=400
        )

    if result.get("expired"):
        return HTMLResponse(
            content=_verification_page("Link Expired", "This verification link has expired. Please request a new one from the registration form."),
            status_code=400
        )

    response = HTMLResponse(
        content=f'<html><head><meta http-equiv="refresh" content="0;url=/"></head><body>Redirecting...</body></html>',
        status_code=200
    )
    set_session_cookie(response, result["email"])
    return response


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status."""
    user = get_authenticated_user(request)
    if user:
        return {
            "authenticated": True,
            "name": user["name"],
            "email": user["email"],
            "remaining_analyses": user["remaining_analyses"],
            "limit_reached": user["limit_reached"],
        }
    return {"authenticated": False}


@router.get("/logout")
async def auth_logout():
    """Clear session cookie."""
    response = JSONResponse(content={"success": True})
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response
