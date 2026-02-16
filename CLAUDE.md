# CLAUDE.md — Coherence Diagnostic Tool

**Created:** 13 February 2026

**Updated:** 14 February 2026

**Status:** Ready for deployment

**Open source:** Yes (users provide own Haiku API key)

---

## What This Tool Does

Takes a design concept (2-8 sentences) and shows what's strong, thin, or unclear across five dimensions. Three-stage pipeline:

1. **Stage 1 (DeBERTa):** Qualifies concept → 5 confidence scores (0.0–1.0)
2. **Stage 2 (Rules):** Converts confidence → 3 severity levels (deterministic)
3. **Stage 3 (Haiku):** Translates severity → plain language diagnosis (API)

**Architectural principle:** AI handles language. Code handles judgment.

---

## Folder Contents

```
coherence-diagnostic/               (714 MB)
├── CLAUDE.md                       ← This file
├── ASSETS.md                       — Asset locations and usage examples
├── README.md                       — GitHub release documentation
├── LICENSE                         — MIT licence
├── .gitignore                      — Git ignore patterns
├── spec.md                         — Full tool specification
├── Dockerfile                      — Container build
├── captain-definition              — CapRover deployment config
├── make-deploy-tar.sh              — Script to create deployment tarball
├── backend/
│   ├── main.py                     — FastAPI application
│   └── requirements.txt            — Python dependencies
├── frontend/
│   └── index.html                  — Single-page application
├── src/
│   └── stage2_rules.py             — Stage 2 deterministic rules
└── models/
    └── deberta-coherence/          — Trained DeBERTa model (Stage 1)
        ├── model.safetensors       (738 MB) — Trained weights
        ├── tokenizer.json          (8.7 MB) — Tokenizer
        ├── config.json             — Model config
        ├── tokenizer_config.json   — Tokenizer config
        ├── spm.model               — SentencePiece model
        ├── added_tokens.json       — Additional tokens
        ├── special_tokens_map.json — Special token mappings
        └── training_args.bin       — Training arguments
```

---

## What's Ready

| Component | Location | Status |
|-----------|----------|--------|
| **DeBERTa model** | `models/deberta-coherence/` | ✅ Trained (98.38% accuracy, 11 Jan 2026) |
| **Stage 2 rules** | `src/stage2_rules.py` | ✅ Updated for float confidence scores |
| **FastAPI backend** | `backend/main.py` | ✅ Built (streaming support) |
| **Frontend** | `frontend/index.html` | ✅ Built (mature design) |
| **Haiku system prompt** | `spec.md` (line 352–420) | ✅ Ready to use |
| **Docker config** | `Dockerfile` | ✅ Ready |
| **CapRover config** | `captain-definition` | ✅ Ready |
| **Password protection** | Backend | ✅ Implemented |

---

## Deployment

### CapRover

```bash
# Create deployment tarball
/opt/homebrew/bin/bash make-deploy-tar.sh

# Upload to CapRover
# Set environment variables:
# - ANTHROPIC_API_KEY: Your Anthropic API key
# - DEMO_PASSWORD: Password for demo access (default: koher2026)
```

### Local Development

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY=your_key_here
export DEMO_PASSWORD=your_password

# Run server
uvicorn backend.main:app --reload

# Open browser
open http://localhost:8000
```

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

## The Five Dimensions

| Dimension | Question | Polarity |
|-----------|----------|----------|
| CLAIM | Is the core claim clearly stated? | Standard |
| EVIDENCE | Is there adequate supporting evidence? | Standard |
| SCOPE | Is the scope appropriately bounded? | Standard |
| ASSUMPTIONS | Are key assumptions acknowledged? | Standard |
| GAPS | Are there critical reasoning gaps? | **Inverted** (high = bad) |

---

## Confidence Thresholds

### Standard Dimensions (CLAIM, EVIDENCE, SCOPE, ASSUMPTIONS)

| Confidence | Severity | Display |
|------------|----------|---------|
| > 0.8 | SOLID | ● Present |
| 0.5 – 0.8 | WORTH_EXAMINING | ◐ Unclear |
| < 0.5 | ATTENTION_NEEDED | ○ Missing |

### GAPS (Inverted)

| Confidence | Severity | Display |
|------------|----------|---------|
| < 0.2 | SOLID | ● Connected |
| 0.2 – 0.5 | WORTH_EXAMINING | ◐ Unclear |
| > 0.5 | ATTENTION_NEEDED | ○ Gaps present |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve frontend |
| `/health` | GET | Health check |
| `/analyse` | POST | Analyse concept (full response) |
| `/analyse/stream` | POST | Analyse concept (streaming diagnosis) |

### POST /analyse

```json
{
  "concept": "My project creates a platform for communities to share local knowledge.",
  "password": "demo_password",
  "include_diagnosis": true
}
```

---

## DeBERTa Model Details

**Base model:** microsoft/deberta-v3-base
**Task:** Multi-label classification (5 dimensions)
**Training date:** 11 January 2026
**Training data:** 4,186 design concepts

### Per-Dimension Accuracy

| Dimension | Accuracy |
|-----------|----------|
| CLAIM | 97.85% |
| EVIDENCE | 98.81% |
| SCOPE | 99.28% |
| ASSUMPTIONS | 97.37% |
| GAPS | 98.57% |
| **Mean** | **98.38%** |

---

## Git Workflow

### After Every Commit

After creating a git commit, **always update `COMMIT-STATUS.md`** with:

```markdown
# Commit Status

**Last commit:** [commit hash]
**Date:** [date and time]
**Message:** [commit message first line]
**Pushed:** Yes / No
**Remote:** [remote URL if pushed]
```

This file tracks the most recent commit state for session continuity across Dropbox sync.

---

## Open Source Strategy

- MIT licence
- Users clone repo and run locally or deploy to own VPS
- Users provide own Anthropic API key for Haiku
- Model weights included in repo (738 MB)

---

*Last updated: 16 February 2026, 18:45*
