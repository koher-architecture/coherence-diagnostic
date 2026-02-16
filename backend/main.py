"""
Coherence Diagnostic Backend

Three-stage pipeline:
1. DeBERTa: Qualifies concept → 5 confidence scores
2. Rules: Converts confidence → severity levels (deterministic)
3. Haiku: Translates severity → plain language diagnosis

Architecture: AI handles language. Code handles judgment.
"""

import os
import sys
import json
import asyncio
import sqlite3
import secrets
import string
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import openai

# Add parent directory to path for stage2_rules import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from stage2_rules import evaluate_concept, format_severity_display, Severity


# =============================================================================
# Configuration
# =============================================================================

MODEL_PATH = Path(__file__).parent.parent / "models" / "deberta-coherence"
DB_PATH = Path(__file__).parent.parent / "data" / "users.db"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable is required")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Limits
MAX_ANALYSES_PER_USER = 10
MAX_NEW_USERS_PER_DAY = 10


# =============================================================================
# Database Management
# =============================================================================

def init_database():
    """Initialise SQLite database for user management."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            password TEXT PRIMARY KEY,
            email TEXT,
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

    conn.commit()
    conn.close()


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(str(DB_PATH))


def generate_password(length: int = 12) -> str:
    """Generate a random password."""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def create_user(email: str = None) -> dict:
    """
    Create a new user with a unique password.
    Returns user info or raises exception if daily limit reached.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    # Check daily limit
    cursor.execute("SELECT users_created FROM daily_stats WHERE date = ?", (today,))
    row = cursor.fetchone()
    users_today = row[0] if row else 0

    if users_today >= MAX_NEW_USERS_PER_DAY:
        conn.close()
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached. Maximum {MAX_NEW_USERS_PER_DAY} new users per day."
        )

    # Generate unique password
    password = generate_password()
    while True:
        cursor.execute("SELECT 1 FROM users WHERE password = ?", (password,))
        if not cursor.fetchone():
            break
        password = generate_password()

    # Create user
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO users (password, email, created_at, usage_count) VALUES (?, ?, ?, 0)",
        (password, email, now)
    )

    # Update daily stats
    cursor.execute("""
        INSERT INTO daily_stats (date, users_created) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET users_created = users_created + 1
    """, (today,))

    conn.commit()
    conn.close()

    return {
        "password": password,
        "email": email,
        "created_at": now,
        "remaining_analyses": MAX_ANALYSES_PER_USER
    }


def verify_user(password: str) -> dict:
    """
    Verify user password and return user info.
    Returns None if invalid, raises 403 if limit reached.
    """
    if not password:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password, email, created_at, usage_count FROM users WHERE password = ?",
        (password,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    usage_count = row[3]
    remaining = MAX_ANALYSES_PER_USER - usage_count

    return {
        "password": row[0],
        "email": row[1],
        "created_at": row[2],
        "usage_count": usage_count,
        "remaining_analyses": remaining,
        "limit_reached": remaining <= 0
    }


def increment_usage(password: str) -> int:
    """Increment usage count for a user. Returns new remaining count."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET usage_count = usage_count + 1 WHERE password = ?",
        (password,)
    )

    cursor.execute("SELECT usage_count FROM users WHERE password = ?", (password,))
    row = cursor.fetchone()

    conn.commit()
    conn.close()

    return MAX_ANALYSES_PER_USER - row[0] if row else 0


def get_all_users() -> list:
    """Get all users (for admin)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT password, email, created_at, usage_count
        FROM users
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "password": row[0],
            "email": row[1],
            "created_at": row[2],
            "usage_count": row[3],
            "remaining_analyses": MAX_ANALYSES_PER_USER - row[3]
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

# Direct AI system prompt (for comparison mode - no 3-stage pipeline)
DIRECT_AI_SYSTEM_PROMPT = """You are a design coherence analyst. A student has submitted a design concept.
Evaluate it across five dimensions:

1. CLAIM: Is there a clear, testable statement about what the design will achieve?
2. EVIDENCE: Is the claim supported by observation or data?
3. SCOPE: Are boundaries defined (who, where, when)?
4. ASSUMPTIONS: Are underlying beliefs acknowledged?
5. GAPS: Does reasoning connect problem to solution without logical jumps?

For each dimension, assess whether it is:
- Strong (clearly present)
- Unclear (something there, but vague)
- Weak/Missing (absent or problematic)

Then provide a brief diagnosis (3-6 sentences) explaining what's weak or unclear and why it matters.

Rules:
- No academic jargon
- No praise for what's strong
- No prescriptive fixes ("you should..." is forbidden)
- Name what's weak or vague and why, specifically
- Use the student's own words where possible"""

# Haiku system prompt (from spec.md)
HAIKU_SYSTEM_PROMPT = """You are a design coherence analyst. A student has submitted
a design concept. Their concept has been scored on five
dimensions by a classification model, and the scores have
been evaluated by deterministic rules.

Your job: explain what the scores reveal about this specific
concept in plain language. You do not score the concept — that
has already been done. You translate scores into explanation.

Three severity levels exist:
- SOLID: dimension is clearly present. Do not discuss it.
- WORTH_EXAMINING: dimension is vague — something is there
  but the writing is too imprecise to confirm. Name what's
  vague and why the tool can't tell.
- ATTENTION_NEEDED: dimension is absent. Name what's missing
  and why it matters.

Rules:
- No academic jargon (no "naming and framing," no
  "reflection-in-action," no citations)
- No praise for what's strong (skip SOLID dimensions)
- No prescriptive fixes ("you should..." is forbidden)
- 3-6 sentences maximum
- Name what's weak or vague and why, specifically
- Use the student's own words where possible
- If asking questions, make them genuine (not rhetorical)
- Do not contradict the scores or severity levels"""


# =============================================================================
# Global State
# =============================================================================

model = None
tokenizer = None
client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown."""
    global model, tokenizer, client

    # Initialise user database
    print("Initialising user database...")
    init_database()

    print(f"Loading DeBERTa model from {MODEL_PATH}...")

    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model path does not exist: {MODEL_PATH}")

    # Load model and tokenizer
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_PATH))
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH))

    # Set model to eval mode
    model.eval()

    # Use GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"Model loaded on {device}")

    # Initialise OpenRouter client if key provided
    if OPENROUTER_API_KEY:
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        )
        print("OpenRouter client initialised")
    else:
        print("Warning: OPENROUTER_API_KEY not set, Stage 3 will be unavailable")

    yield

    # Cleanup
    print("Shutting down...")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Coherence Diagnostic",
    description="Design concept coherence analysis using Koher architecture",
    version="1.1.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalyseRequest(BaseModel):
    concept: str = Field(..., min_length=10, max_length=2000, description="Design concept text (2-8 sentences)")
    password: Optional[str] = Field(None, description="Demo password for protected access")
    include_diagnosis: bool = Field(True, description="Whether to include Haiku diagnosis")


class ScoreResponse(BaseModel):
    dimension: str
    confidence: float
    severity: str
    display: str


class AnalyseResponse(BaseModel):
    concept: str
    scores: list[ScoreResponse]
    evaluation: dict
    diagnosis: Optional[str] = None
    remaining_analyses: Optional[int] = None


class DirectAIRequest(BaseModel):
    concept: str = Field(..., min_length=10, max_length=2000, description="Design concept text (2-8 sentences)")
    password: Optional[str] = Field(None, description="Demo password for protected access")


class DirectAIResponse(BaseModel):
    concept: str
    response: str
    model: str = "anthropic/claude-haiku-4.5"
    remaining_analyses: Optional[int] = None


# =============================================================================
# Password Verification
# =============================================================================

def verify_password(password: Optional[str]) -> dict:
    """
    Verify user password and check usage limits.
    Returns user info dict or None if invalid.
    Raises HTTPException if limit reached.
    """
    user = verify_user(password)

    if not user:
        return None

    if user["limit_reached"]:
        raise HTTPException(
            status_code=403,
            detail="Analysis limit reached. You have used all 10 analyses."
        )

    return user


def verify_admin(password: Optional[str]) -> bool:
    """Check if password matches admin password."""
    return password == ADMIN_PASSWORD


# =============================================================================
# Stage 1: DeBERTa Inference
# =============================================================================

DIMENSION_ORDER = ["CLAIM", "EVIDENCE", "SCOPE", "ASSUMPTIONS", "GAPS"]


def run_stage1(concept: str) -> dict[str, float]:
    """
    Run DeBERTa inference on concept text.

    Returns confidence scores (0.0-1.0) for each dimension.
    """
    global model, tokenizer

    device = next(model.parameters()).device

    # Tokenise
    inputs = tokenizer(
        concept,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Inference
    with torch.no_grad():
        outputs = model(**inputs)
        confidence = torch.sigmoid(outputs.logits).cpu().numpy()[0]

    # Map to dimension names
    return {dim: float(conf) for dim, conf in zip(DIMENSION_ORDER, confidence)}


# =============================================================================
# Stage 3: Haiku Diagnosis
# =============================================================================

def build_haiku_prompt(concept: str, evaluation: dict) -> str:
    """Build the user prompt for Haiku."""
    severity = evaluation["severity_levels"]

    severity_text = "\n".join([
        f"- {dim}: {sev}"
        for dim, sev in severity.items()
    ])

    stage2_json = json.dumps({
        "claim_evidence": evaluation["claim_evidence"],
        "scope": evaluation["scope"],
        "assumptions": evaluation["assumptions"],
        "gaps": evaluation["gaps"],
        "summary": evaluation["summary"]
    }, indent=2)

    return f"""Concept: {concept}

Severity:
{severity_text}

Stage 2 evaluation:
{stage2_json}"""


MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def stream_diagnosis(concept: str, evaluation: dict):
    """Stream diagnosis from Haiku via OpenRouter with retry logic."""
    global client

    if not client:
        yield "data: [Diagnosis unavailable - API key not configured]\n\n"
        return

    user_prompt = build_haiku_prompt(concept, evaluation)

    for attempt in range(MAX_RETRIES):
        try:
            stream = client.chat.completions.create(
                model="anthropic/claude-haiku-4.5",
                max_tokens=500,
                messages=[
                    {"role": "system", "content": HAIKU_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'text': chunk.choices[0].delta.content})}\n\n"

            yield "data: [DONE]\n\n"
            return  # Success, exit function

        except openai.APIStatusError as e:
            if e.status_code == 529 or "overloaded" in str(e).lower():
                if attempt < MAX_RETRIES - 1:
                    yield f"data: {json.dumps({'info': f'API busy, retrying ({attempt + 1}/{MAX_RETRIES})...'})}\n\n"
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return


async def get_full_diagnosis(concept: str, evaluation: dict) -> str:
    """Get complete diagnosis (non-streaming) via OpenRouter with retry logic."""
    global client

    if not client:
        return "[Diagnosis unavailable - API key not configured]"

    user_prompt = build_haiku_prompt(concept, evaluation)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="anthropic/claude-haiku-4.5",
                max_tokens=500,
                messages=[
                    {"role": "system", "content": HAIKU_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content

        except openai.APIStatusError as e:
            if e.status_code == 529 or "overloaded" in str(e).lower():
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            return f"[Error: {str(e)}]"

        except Exception as e:
            return f"[Error: {str(e)}]"

    return "[Error: Max retries exceeded]"


# =============================================================================
# Display Formatting
# =============================================================================

SEVERITY_LABELS = {
    "CLAIM": {
        "SOLID": "Present",
        "WORTH_EXAMINING": "Unclear",
        "ATTENTION_NEEDED": "Unclear or missing"
    },
    "EVIDENCE": {
        "SOLID": "Supported",
        "WORTH_EXAMINING": "Unclear",
        "ATTENTION_NEEDED": "Absent"
    },
    "SCOPE": {
        "SOLID": "Bounded",
        "WORTH_EXAMINING": "Unclear",
        "ATTENTION_NEEDED": "Unbounded"
    },
    "ASSUMPTIONS": {
        "SOLID": "Acknowledged",
        "WORTH_EXAMINING": "Unclear",
        "ATTENTION_NEEDED": "Hidden"
    },
    "GAPS": {
        "SOLID": "Connected",
        "WORTH_EXAMINING": "Unclear",
        "ATTENTION_NEEDED": "Gaps present"
    }
}

SEVERITY_SYMBOLS = {
    "SOLID": "●",
    "WORTH_EXAMINING": "◐",
    "ATTENTION_NEEDED": "○"
}


def format_score(dimension: str, confidence: float, severity: str) -> ScoreResponse:
    """Format a single dimension score for response."""
    symbol = SEVERITY_SYMBOLS.get(severity, "?")
    label = SEVERITY_LABELS.get(dimension, {}).get(severity, severity)
    display = f"{symbol} {label}"

    if severity == "ATTENTION_NEEDED":
        display += " ← Needs attention"

    return ScoreResponse(
        dimension=dimension,
        confidence=round(confidence, 3),
        severity=severity,
        display=display
    )


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "haiku_available": client is not None
    }


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse_concept(request: AnalyseRequest):
    """
    Analyse a design concept.

    Returns scores, evaluation, and optional diagnosis.
    """
    # Verify password and check limits
    user = verify_password(request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Stage 1: DeBERTa inference
    confidence_scores = run_stage1(request.concept)

    # Stage 2: Deterministic rules
    evaluation = evaluate_concept(confidence_scores)

    # Format scores for response
    scores = [
        format_score(dim, confidence_scores[dim], evaluation["severity_levels"][dim])
        for dim in DIMENSION_ORDER
    ]

    # Stage 3: Haiku diagnosis (optional)
    diagnosis = None
    if request.include_diagnosis:
        diagnosis = await get_full_diagnosis(request.concept, evaluation)

    # Increment usage and get remaining count
    remaining = increment_usage(request.password)

    return AnalyseResponse(
        concept=request.concept,
        scores=scores,
        evaluation=evaluation,
        diagnosis=diagnosis,
        remaining_analyses=remaining
    )


@app.post("/analyse/stream")
async def analyse_concept_stream(request: AnalyseRequest):
    """
    Analyse a design concept with streaming diagnosis.

    Returns scores immediately, then streams diagnosis via SSE.
    """
    # Verify password and check limits
    user = verify_password(request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Stage 1: DeBERTa inference
    confidence_scores = run_stage1(request.concept)

    # Stage 2: Deterministic rules
    evaluation = evaluate_concept(confidence_scores)

    # Format scores for response
    scores = [
        format_score(dim, confidence_scores[dim], evaluation["severity_levels"][dim])
        for dim in DIMENSION_ORDER
    ]

    # Increment usage and get remaining count
    remaining = increment_usage(request.password)

    # Build initial response with scores
    initial_data = {
        "concept": request.concept,
        "scores": [s.model_dump() for s in scores],
        "evaluation": evaluation,
        "remaining_analyses": remaining
    }

    async def generate():
        # First, send scores
        yield f"data: {json.dumps({'type': 'scores', 'data': initial_data})}\n\n"

        # Then stream diagnosis
        async for chunk in stream_diagnosis(request.concept, evaluation):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api")
async def api_info():
    """API info endpoint."""
    return {
        "name": "Coherence Diagnostic API",
        "version": "1.0.0",
        "architecture": "Koher (AI handles language, Code handles judgment)",
        "endpoints": {
            "POST /analyse": "Analyse concept (full response)",
            "POST /analyse/stream": "Analyse concept (streaming diagnosis)",
            "POST /analyse/direct": "Direct AI analysis (no pipeline)",
            "GET /samples": "Get sample design concepts",
            "GET /health": "Health check"
        }
    }


# =============================================================================
# Direct AI Endpoint (for comparison)
# =============================================================================

async def get_direct_ai_response(concept: str) -> str:
    """Get direct AI analysis without 3-stage pipeline."""
    global client

    if not client:
        return "[Direct AI unavailable - API key not configured]"

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="anthropic/claude-haiku-4.5",
                max_tokens=800,
                messages=[
                    {"role": "system", "content": DIRECT_AI_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Design concept:\n\n{concept}"}
                ]
            )
            return response.choices[0].message.content

        except openai.APIStatusError as e:
            if e.status_code == 529 or "overloaded" in str(e).lower():
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            return f"[Error: {str(e)}]"

        except Exception as e:
            return f"[Error: {str(e)}]"

    return "[Error: Max retries exceeded]"


@app.post("/analyse/direct", response_model=DirectAIResponse)
async def analyse_direct(request: DirectAIRequest):
    """
    Analyse a design concept using direct AI (no 3-stage pipeline).

    This endpoint sends the concept directly to Claude for evaluation,
    bypassing the DeBERTa qualification and deterministic rules.
    Used for comparison with the Koher architecture.
    """
    # Verify password and check limits
    user = verify_password(request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Direct AI analysis (no usage increment — counted by /analyse endpoint in comparison mode)
    response = await get_direct_ai_response(request.concept)

    remaining = user["remaining_analyses"]

    return DirectAIResponse(
        concept=request.concept,
        response=response,
        remaining_analyses=remaining
    )


# =============================================================================
# Sample Concepts
# =============================================================================

SAMPLE_CONCEPTS = {
    "strong": [
        "Working parents with children aged 6-12 in dual-income households struggle to coordinate school pickup schedules. In interviews with 15 families, 12 mentioned last-minute changes causing stress. I'm designing a shared family calendar that syncs pickup responsibilities between parents and sends reminders 30 minutes before transitions. This assumes both parents have smartphones and reliable data connections.",
        "First-generation university students often don't know which campus services exist or how to access them. A survey of 200 first-gen students showed 73% were unaware of free tutoring until their second year. I'm proposing a welcome guide delivered during orientation week that maps all support services with student testimonials. This assumes students will read materials given during an already overwhelming week.",
        "Rural elderly patients (65+) in Gujarat miss medication doses because pill bottles are hard to open and labels are too small. Observations in 8 homes revealed all patients relied on family members to manage medications. I'm designing a voice-activated dispenser that announces medication times in Gujarati. This requires consistent electricity and assumes patients live alone but have family visit weekly."
    ],
    "weak": [
        "I'm designing an app that helps people be more productive. Everyone struggles with productivity these days, and my app will solve this problem by using AI to help users manage their time better.",
        "My project is about making education more accessible. There are many people who don't have access to good education, so I'm building a platform that will change this.",
        "I want to create a sustainable solution for urban living. Cities are becoming more crowded and we need better ways to live. My design will address this through innovative technology."
    ],
    "middle": [
        "Young professionals aged 25-35 report feeling overwhelmed by financial decisions. I'm designing a budgeting app that simplifies investment choices. The app will use machine learning to predict spending patterns. I believe this will help users feel more confident about money.",
        "Hospital waiting rooms cause anxiety for patients. My project creates a calming digital environment using ambient sounds and lighting. This is based on research about environmental psychology in healthcare settings.",
        "Small business owners struggle with social media marketing. I'm building a tool that automates content creation and scheduling. This targets businesses with fewer than 10 employees who don't have dedicated marketing staff."
    ]
}

import random

@app.get("/samples")
async def get_sample_concepts():
    """
    Get sample design concepts for testing.

    Returns one random concept from each category (strong, weak, middle).
    """
    return {
        "strong": random.choice(SAMPLE_CONCEPTS["strong"]),
        "weak": random.choice(SAMPLE_CONCEPTS["weak"]),
        "middle": random.choice(SAMPLE_CONCEPTS["middle"])
    }


# =============================================================================
# Admin Endpoints
# =============================================================================

class AdminLoginRequest(BaseModel):
    password: str = Field(..., description="Admin password")


class CreateUserRequest(BaseModel):
    email: Optional[str] = Field(None, description="Optional email for the new user")
    admin_password: str = Field(..., description="Admin password for authentication")


class UserInfo(BaseModel):
    password: str
    email: Optional[str]
    created_at: str
    usage_count: int
    remaining_analyses: int


class UserStatusRequest(BaseModel):
    password: str = Field(..., description="User password")


@app.post("/user/status")
async def get_user_status(request: UserStatusRequest):
    """
    Get user status including remaining analyses.

    Returns user info without consuming an analysis.
    """
    user = verify_user(request.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid password")

    return {
        "valid": True,
        "usage_count": user["usage_count"],
        "remaining_analyses": user["remaining_analyses"],
        "limit_reached": user["limit_reached"]
    }


@app.post("/admin/login")
async def admin_login(request: AdminLoginRequest):
    """Verify admin password."""
    if not verify_admin(request.password):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return {"success": True, "message": "Admin authenticated"}


@app.get("/admin/users")
async def list_users(admin_password: str):
    """List all users (admin only)."""
    if not verify_admin(admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    users = get_all_users()
    return {"users": users, "total": len(users)}


@app.post("/admin/create-user")
async def create_new_user(request: CreateUserRequest):
    """Create a new user (admin only)."""
    if not verify_admin(request.admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    try:
        user = create_user(request.email)
        return {
            "success": True,
            "user": user,
            "message": f"User created with password: {user['password']}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/stats")
async def admin_stats(admin_password: str):
    """Get usage statistics (admin only)."""
    if not verify_admin(admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    stats = get_daily_stats()
    users = get_all_users()

    total_usage = sum(u["usage_count"] for u in users)
    active_users = sum(1 for u in users if u["usage_count"] > 0)

    return {
        "daily": stats,
        "totals": {
            "total_users": len(users),
            "active_users": active_users,
            "total_analyses": total_usage,
            "max_analyses_per_user": MAX_ANALYSES_PER_USER,
            "max_new_users_per_day": MAX_NEW_USERS_PER_DAY
        }
    }


ADMIN_PAGE_PATH = Path(__file__).parent.parent / "frontend" / "admin.html"


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """Serve the admin page."""
    if ADMIN_PAGE_PATH.exists():
        return FileResponse(ADMIN_PAGE_PATH)
    return HTMLResponse(content="<h1>Admin page not found</h1>", status_code=404)


# =============================================================================
# Static Files & Frontend
# =============================================================================

FRONTEND_PATH = Path(__file__).parent.parent / "frontend"


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend index.html."""
    index_path = FRONTEND_PATH / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Frontend not found"}


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
