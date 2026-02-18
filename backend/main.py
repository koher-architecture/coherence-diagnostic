"""
Coherence Diagnostic Backend

Three-stage pipeline:
1. DeBERTa: Qualifies concept → 5 confidence scores
2. Rules: Converts confidence → severity levels (deterministic)
3. Haiku: Translates severity → plain language diagnosis

Architecture: AI handles language. Code handles judgment.

Module Structure:
- main.py: Core analysis pipeline (this file)
- auth.py: Email verification, user management (loaded if ENABLE_AUTH=1)
- admin.py: Admin panel (loaded if ENABLE_AUTH=1)

Feature toggle via config.py / config.env:
- ENABLE_AUTH=0: Open access — anyone can use the tool
- ENABLE_AUTH=1: Gated access — email verification + admin panel
"""

import json
import asyncio
import random
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import openai

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    ENABLE_AUTH,
    OPENROUTER_API_KEY, MODEL_PATH,
    validate_config, print_config_summary
)

# Add src directory to path for stage2_rules import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from stage2_rules import evaluate_concept, Severity


# =============================================================================
# Prompts
# =============================================================================

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


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown."""
    global model, tokenizer, client

    # Validate configuration
    print_config_summary()
    validate_config()

    # Initialise database if auth is enabled
    if ENABLE_AUTH:
        from backend.auth import init_database
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

    # Initialise OpenRouter client
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
    version="2.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conditionally include auth router
if ENABLE_AUTH:
    from backend.auth import router as auth_router
    app.include_router(auth_router)
    print("Auth module loaded")

# Conditionally include admin router
if ENABLE_AUTH:
    from backend.admin import router as admin_router
    app.include_router(admin_router)
    print("Admin module loaded")


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalyseRequest(BaseModel):
    concept: str = Field(..., min_length=10, max_length=2000, description="Design concept text (2-8 sentences)")
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


class DirectAIResponse(BaseModel):
    concept: str
    response: str
    model: str = "anthropic/claude-haiku-4.5"
    remaining_analyses: Optional[int] = None


# =============================================================================
# Auth Helpers (conditional)
# =============================================================================

def get_user_for_request(request: Request) -> Optional[dict]:
    """
    Get user for request if auth is enabled.
    Returns None if auth is disabled (open access).
    """
    if not ENABLE_AUTH:
        return None

    from backend.auth import get_authenticated_user
    return get_authenticated_user(request)


def require_auth_if_enabled(request: Request) -> Optional[dict]:
    """
    Require authentication if auth is enabled.
    Returns user dict if auth enabled, None if auth disabled.
    """
    if not ENABLE_AUTH:
        return None

    from backend.auth import require_auth
    return require_auth(request)


def increment_usage_if_enabled(user: Optional[dict]) -> Optional[int]:
    """
    Increment usage count if auth is enabled.
    Returns remaining count or None if auth disabled.
    """
    if not ENABLE_AUTH or user is None:
        return None

    from backend.auth import increment_usage
    return increment_usage(user["email"])


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
RETRY_DELAY = 2


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
            return

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
# Direct AI (for comparison)
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
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "haiku_available": client is not None,
        "auth_enabled": ENABLE_AUTH,
        "admin_enabled": ENABLE_AUTH
    }


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse_concept(request: AnalyseRequest, req: Request):
    """
    Analyse a design concept.
    Returns scores, evaluation, and optional diagnosis.
    """
    user = require_auth_if_enabled(req)

    if user and user.get("limit_reached"):
        raise HTTPException(
            status_code=403,
            detail="Analysis limit reached. You have used all your analyses."
        )

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

    # Increment usage if auth enabled
    remaining = increment_usage_if_enabled(user)

    return AnalyseResponse(
        concept=request.concept,
        scores=scores,
        evaluation=evaluation,
        diagnosis=diagnosis,
        remaining_analyses=remaining
    )


@app.post("/analyse/stream")
async def analyse_concept_stream(request: AnalyseRequest, req: Request):
    """
    Analyse a design concept with streaming diagnosis.
    Returns scores immediately, then streams diagnosis via SSE.
    """
    user = require_auth_if_enabled(req)

    if user and user.get("limit_reached"):
        raise HTTPException(
            status_code=403,
            detail="Analysis limit reached. You have used all your analyses."
        )

    # Stage 1: DeBERTa inference
    confidence_scores = run_stage1(request.concept)

    # Stage 2: Deterministic rules
    evaluation = evaluate_concept(confidence_scores)

    # Format scores for response
    scores = [
        format_score(dim, confidence_scores[dim], evaluation["severity_levels"][dim])
        for dim in DIMENSION_ORDER
    ]

    # Increment usage if auth enabled
    remaining = increment_usage_if_enabled(user)

    # Build initial response with scores
    initial_data = {
        "concept": request.concept,
        "scores": [s.model_dump() for s in scores],
        "evaluation": evaluation,
        "remaining_analyses": remaining
    }

    async def generate():
        yield f"data: {json.dumps({'type': 'scores', 'data': initial_data})}\n\n"
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


@app.post("/analyse/direct", response_model=DirectAIResponse)
async def analyse_direct(request: DirectAIRequest, req: Request):
    """
    Analyse a design concept using direct AI (no 3-stage pipeline).
    Used for comparison with the Koher architecture.
    """
    user = require_auth_if_enabled(req)

    if user and user.get("limit_reached"):
        raise HTTPException(
            status_code=403,
            detail="Analysis limit reached. You have used all your analyses."
        )

    response = await get_direct_ai_response(request.concept)
    remaining = user["remaining_analyses"] if user else None

    return DirectAIResponse(
        concept=request.concept,
        response=response,
        remaining_analyses=remaining
    )


@app.get("/api")
async def api_info():
    """API info endpoint."""
    endpoints = {
        "POST /analyse": "Analyse concept (full response)",
        "POST /analyse/stream": "Analyse concept (streaming diagnosis)",
        "POST /analyse/direct": "Direct AI analysis (no pipeline)",
        "GET /samples": "Get sample design concepts",
        "GET /health": "Health check",
    }

    if ENABLE_AUTH:
        endpoints.update({
            "POST /auth/register": "Register with email",
            "GET /auth/verify/{token}": "Verify email",
            "GET /auth/status": "Check auth status",
            "GET /auth/logout": "Logout"
        })

    if ENABLE_AUTH:
        endpoints.update({
            "GET /admin": "Admin panel",
            "POST /admin/login": "Admin login",
            "GET /admin/users": "List users",
            "GET /admin/waitlist": "List waitlist",
            "GET /admin/stats": "Usage statistics"
        })

    return {
        "name": "Coherence Diagnostic API",
        "version": "2.0.0",
        "architecture": "Koher (AI handles language, Code handles judgment)",
        "auth_enabled": ENABLE_AUTH,
        "admin_enabled": ENABLE_AUTH,
        "endpoints": endpoints
    }


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
# Static Files & Frontend
# =============================================================================

FRONTEND_PATH = Path(__file__).parent.parent / "frontend"


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend index.html."""
    # Serve different frontend based on auth mode
    if ENABLE_AUTH:
        index_path = FRONTEND_PATH / "index.html"
    else:
        index_path = FRONTEND_PATH / "index-open.html"
        # Fall back to regular index if open version doesn't exist
        if not index_path.exists():
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
