# Coherence Diagnostic

Analyse design concepts for coherence. See what's strong, thin, or unclear.

**Part of [Koher](https://koher.app) — AI handles language. Code handles judgment. Humans make decisions.**

---

## 🚀 Get Started

### Try It Online

**[→ Launch Coherence Diagnostic](https://coherence-demo.koher.app)**

Hosted instance available by invitation. [Request access](mailto:hello@koher.app?subject=Coherence%20Diagnostic%20Access%20Request&body=I%27d%20like%20to%20try%20the%20Coherence%20Diagnostic%20tool.)

### Run Locally

```bash
git clone https://github.com/koher-architecture/coherence-diagnostic.git
cd coherence-diagnostic
pip install -r backend/requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
uvicorn backend.main:app --reload
# Open http://localhost:8000
```

Requires Python 3.11+, ~750MB disk (for model weights), and an [Anthropic API key](https://console.anthropic.com/).

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
- Anthropic API key (for Stage 3 diagnosis)

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

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-key-here"

# Run the server
uvicorn backend.main:app --reload
```

Open `http://localhost:8000` in your browser.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | For Stage 3 diagnosis (Haiku) |
| `DEMO_PASSWORD` | No | Password protection (default: none) |
| `SESSION_SECRET` | No | For signed cookies |

### Docker

```bash
# Build
docker build -t coherence-diagnostic .

# Run
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=your_key \
  -e DEMO_PASSWORD=your_password \
  coherence-diagnostic
```

---

## File Structure

```
coherence-diagnostic/
├── README.md                     # This file
├── LICENSE                       # MIT
├── Dockerfile                    # Container build
├── captain-definition            # CapRover deployment config
├── backend/
│   ├── main.py                   # FastAPI server
│   └── requirements.txt          # Python dependencies
├── frontend/
│   └── index.html                # Single-page application
├── src/
│   └── stage2_rules.py           # Deterministic judgment rules
└── models/
    └── deberta-coherence/        # Trained DeBERTa model (~738MB)
        ├── model.safetensors
        ├── config.json
        └── ...
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

### `POST /analyse`

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

### `POST /analyse/stream`

Same as above, but streams the diagnosis via Server-Sent Events.

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
