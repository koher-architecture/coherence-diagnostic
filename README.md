# Coherence Diagnostic

Analyse design concepts for coherence. See what's strong, thin, or unclear.

**Part of [Koher](https://koher.app) — AI handles language. Code handles judgment. Humans make decisions.**

---

## Quick Start

### Run Locally (Open Access Mode)

```bash
git clone https://github.com/koher-architecture/coherence-diagnostic.git
cd coherence-diagnostic
pip install -r backend/requirements.txt
cp config.env.example config.env
# Edit config.env: add your OPENROUTER_API_KEY
uvicorn backend.main:app --reload
# Open http://localhost:8000
```

Requires Python 3.11+, ~750MB disk (for model weights), and an [OpenRouter API key](https://openrouter.ai/).

---

## What It Does

Paste a design concept. Get a three-state evaluation across five dimensions:

| Dimension | What It Measures |
|-----------|------------------|
| **Claim** | Is there a clear, testable statement? |
| **Evidence** | Is the claim supported by observation or data? |
| **Scope** | Are boundaries defined (who, where, when)? |
| **Assumptions** | Are underlying beliefs acknowledged? |
| **Gaps** | Does reasoning connect problem to solution? |

Each dimension receives one of three states:
- **● Solid** — clearly present
- **◐ Worth examining** — something there, but vague
- **○ Needs attention** — absent or unclear

---

## Configuration

All configuration is managed through `config.env` (copy from `config.env.example`).

### Feature Toggle

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| `ENABLE_AUTH` | `0` / `1` | `0` | Gated access: email verification + admin panel |

### Deployment Modes

#### Open Access (Default)

Anyone can use the tool. No registration required.

```env
ENABLE_AUTH=0
OPENROUTER_API_KEY=your_key
```

#### Gated Access

Users must verify email. Usage limits apply. Admin panel at `/admin`.

```env
ENABLE_AUTH=1
OPENROUTER_API_KEY=your_key
SESSION_SECRET=your_64_char_secret
ADMIN_PASSWORD=your_admin_password
MAX_ANALYSES_PER_USER=10
MAX_NEW_USERS_PER_DAY=10
```

### Environment Variables

#### Required (Always)

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | For Stage 3 diagnosis (Claude Haiku via OpenRouter) |

#### Required (if ENABLE_AUTH=1)

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET` | 64-character secret for signing session cookies |
| `ADMIN_PASSWORD` | Password for accessing `/admin` panel |
| `BASE_URL` | Base URL for verification emails (e.g., `https://yoursite.com`) |

#### Optional (if ENABLE_AUTH=1)

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_ANALYSES_PER_USER` | `10` | Analyses per user account |
| `MAX_NEW_USERS_PER_DAY` | `10` | New signups per day |
| `SMTP_HOST` | — | SMTP server for verification emails |
| `SMTP_PORT` | `587` | SMTP port (usually 587 for TLS) |
| `SMTP_USERNAME` | — | SMTP username or API key |
| `SMTP_PASSWORD` | — | SMTP password or API key |
| `SMTP_FROM_EMAIL` | `noreply@example.com` | Sender email address |
| `SMTP_FROM_NAME` | `Coherence Diagnostic` | Sender display name |

**Note:** If SMTP is not configured, verification links are printed to console (useful for development).

**SMTP Provider Examples:**
- **SendGrid:** `SMTP_HOST=smtp.sendgrid.net`, `SMTP_USERNAME=apikey`, `SMTP_PASSWORD=your_api_key`
- **Mailgun:** `SMTP_HOST=smtp.mailgun.org`, use your Mailgun credentials
- **AWS SES:** `SMTP_HOST=email-smtp.{region}.amazonaws.com`, use IAM SMTP credentials
- **Postmark:** `SMTP_HOST=smtp.postmarkapp.com`, use your server API token
- **Gmail:** `SMTP_HOST=smtp.gmail.com`, use an app password (not your regular password)

---

## File Structure

```
coherence-diagnostic/
├── README.md                     # This file
├── LICENSE                       # MIT
├── config.py                     # Configuration loader (feature flags, validation)
├── config.env.example            # Configuration template
├── Dockerfile                    # Container build
├── entrypoint.sh                 # Downloads model on first deploy, starts server
├── backend/
│   ├── main.py                   # FastAPI server (conditionally loads auth/admin)
│   ├── auth.py                   # Auth module (email verification, sessions, limits)
│   ├── admin.py                  # Admin module (user listing, stats)
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── index.html                # Full frontend (with auth screens)
│   ├── index-open.html           # Open access frontend (no auth)
│   └── admin.html                # Admin panel
├── src/
│   └── stage2_rules.py           # Deterministic judgment rules
└── models/
    └── deberta-coherence/        # Trained DeBERTa model (~738MB)
        ├── model.safetensors
        ├── config.json
        └── ...
```

---

## Module Architecture

The tool is separated into three modules that load conditionally:

### Core Tool (`backend/main.py`)

Always loaded. Contains:
- FastAPI application setup
- DeBERTa model loading
- `/analyse`, `/analyse/stream`, `/analyse/direct` endpoints
- `/samples`, `/health` endpoints
- Frontend serving

### Auth Module (`backend/auth.py`)

Only loaded if `ENABLE_AUTH=1`. Contains:
- Email verification flow (`/auth/register`, `/auth/verify/{token}`)
- Session cookie management (`/auth/status`, `/auth/logout`)
- User registration and limits
- Database initialisation (SQLite)

### Admin Module (`backend/admin.py`)

Only loaded if `ENABLE_AUTH=1`. Contains:
- Admin authentication (`/admin/login`)
- User listing (`/admin/users`)
- Waitlist management (`/admin/waitlist`)
- Usage statistics (`/admin/stats`)
- Admin panel serving (`/admin`)

---

## Architecture

This tool demonstrates the Koher three-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: Qualification                                     │
│  DeBERTa multi-label classifier (98.38% accuracy)           │
│  Input: concept text → Output: confidence scores (0.0–1.0)  │
│  Principle: AI reads language patterns                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: Deterministic Rules                               │
│  Pure Python code — no AI                                   │
│  Input: confidence scores → Output: severity levels         │
│  Thresholds: >0.8 = SOLID, 0.5–0.8 = EXAMINE, <0.5 = ATTENTION │
│  Principle: Code handles judgment                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: Language Interface                                │
│  Claude Haiku explains the judgment                         │
│  Input: severity levels → Output: plain language diagnosis  │
│  Principle: AI narrates decisions already made              │
└─────────────────────────────────────────────────────────────┘
```

**Why separate layers?**
- Stage 1 (AI): Good at pattern recognition across language
- Stage 2 (Code): Judgment is auditable, reproducible, explicit
- Stage 3 (AI): Good at narrating decisions already made

When you ask AI to "judge whether this is good," you lose auditability. When you separate the layers, you gain it back.

---

## Running Locally

### Requirements

- Python 3.11+
- ~750MB disk space (for DeBERTa model)
- OpenRouter API key (for Stage 3 diagnosis via Claude Haiku)

### Setup

```bash
# Clone the repository
git clone https://github.com/koher-architecture/coherence-diagnostic.git
cd coherence-diagnostic

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Create configuration
cp config.env.example config.env
# Edit config.env with your settings

# Run the server
uvicorn backend.main:app --reload
```

Open `http://localhost:8000` in your browser.

### Docker

```bash
# Build
docker build -t coherence-diagnostic .

# Run (open access mode)
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=your_key \
  -v coherence-models:/app/models \
  coherence-diagnostic

# Run (gated access mode)
docker run -p 8000:8000 \
  -e ENABLE_AUTH=1 \
  -e OPENROUTER_API_KEY=your_key \
  -e SESSION_SECRET=your_64_char_secret \
  -e ADMIN_PASSWORD=your_admin_password \
  -e BASE_URL=https://yoursite.com \
  -v coherence-models:/app/models \
  -v coherence-data:/app/data \
  coherence-diagnostic
```

**Note:** The DeBERTa model (~750MB) downloads automatically on first deploy. It persists in the `/app/models` volume — subsequent container restarts use the cached model.

### Docker Compose

```yaml
version: '3.8'
services:
  coherence:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      # Uncomment for gated access:
      # - ENABLE_AUTH=1
      # - SESSION_SECRET=${SESSION_SECRET}
      # - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      # - BASE_URL=https://yoursite.com
    volumes:
      - coherence-models:/app/models
      - coherence-data:/app/data

volumes:
  coherence-models:
  coherence-data:
```

---

## The Five Dimensions

### Claim
A design claim is a testable statement about what the design will achieve. Not a description of what you're making — a statement about what will change.

- **● Present**: "Parents will spend less time coordinating schedules"
- **○ Missing**: "I'm designing a calendar app"

### Evidence
Evidence connects claims to reality. Observations, interviews, data — something outside your own assumptions.

- **● Supported**: "In interviews, 8/10 parents mentioned coordination as their main frustration"
- **○ Absent**: "I think parents are frustrated"

### Scope
Scope defines boundaries. Who is this for? Where does it apply? What's excluded?

- **● Bounded**: "Working parents with children aged 6–12 in dual-income households"
- **○ Unbounded**: "Parents" or "Everyone"

### Assumptions
Assumptions are beliefs you haven't verified. Acknowledging them is strength, not weakness.

- **● Acknowledged**: "This assumes parents have smartphones and reliable internet"
- **○ Hidden**: No mention of what must be true for the design to work

### Gaps
Gaps are logical jumps — places where reasoning skips steps between problem and solution.

- **● Connected**: Clear path from research finding → insight → design decision
- **○ Present**: "Users are frustrated, so I'm building a chatbot"

---

## API Endpoints

### Core Endpoints

#### `POST /analyse`

Analyse a design concept and return scores with diagnosis.

**Request:**
```json
{
  "concept": "Your design concept text here...",
  "include_diagnosis": true
}
```

**Response:**
```json
{
  "concept": "...",
  "scores": [
    {"dimension": "CLAIM", "confidence": 0.85, "severity": "SOLID", "display": "● Present"},
    {"dimension": "EVIDENCE", "confidence": 0.32, "severity": "ATTENTION_NEEDED", "display": "○ Absent ← Needs attention"}
  ],
  "evaluation": { ... },
  "diagnosis": "The concept states a clear claim about..."
}
```

#### `POST /analyse/stream`

Same as above, but streams the diagnosis via Server-Sent Events.

#### `POST /analyse/direct`

Direct AI analysis (bypasses Koher architecture for comparison).

### Auth Endpoints (if ENABLE_AUTH=1)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register user, send verification email |
| `/auth/verify/{token}` | GET | Verify email via magic link |
| `/auth/status` | GET | Check authentication status |
| `/auth/logout` | GET | Clear session cookie |

### Admin Endpoints (if ENABLE_AUTH=1)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin` | GET | Serve admin panel |
| `/admin/login` | POST | Verify admin password |
| `/admin/users` | GET | List all users |
| `/admin/waitlist` | GET | List waitlist entries |
| `/admin/stats` | GET | Usage statistics |

---

## Stage 2 Rules

The judgment logic lives in `src/stage2_rules.py`. It's pure Python — no AI, no network calls, no randomness.

**Thresholds:**
```python
# Standard dimensions (high confidence = good)
THRESHOLD_SOLID = 0.8       # > 0.8 = SOLID
THRESHOLD_EXAMINE = 0.5     # 0.5–0.8 = WORTH_EXAMINING
                            # < 0.5 = ATTENTION_NEEDED

# GAPS has inverted polarity (high confidence = gaps present = bad)
GAPS_THRESHOLD_SOLID = 0.2      # < 0.2 = SOLID
GAPS_THRESHOLD_EXAMINE = 0.5    # 0.2–0.5 = WORTH_EXAMINING
                                # > 0.5 = ATTENTION_NEEDED
```

**Relationship rules:**
- Claim without evidence → "You've made a claim but haven't shown how you know it's true"
- Evidence without claim → "You've gathered evidence but haven't stated what you're claiming"
- Both missing → "Neither a clear claim nor supporting evidence is present"

---

## Model Details

**Architecture:** DeBERTa-v3-base, fine-tuned for multi-label classification

**Training:**
- 5,600 annotated design concepts
- 5 binary labels (one per dimension)
- Validation accuracy: 98.38%

**Size:** ~738MB (model.safetensors: 705MB)

---

## Cost Analysis (Haiku Stage 3)

| Scale | Analyses/month | Cost |
|-------|----------------|------|
| Small class (25 × 3) | 75 | ₹6 |
| Weekly (100/week) | 400 | ₹32 |
| Daily (100/day) | 3,000 | ₹240 |

---

## Licence

MIT — use it, modify it, ship it.

---

## Part of Koher

This tool demonstrates the Koher architecture. More tools ship monthly.

- **Website:** [koher.app](https://koher.app)
- **All tools:** [github.com/koher-architecture](https://github.com/koher-architecture)

*Built by [Prayas Abhinav](https://prayasabhinav.net)*
