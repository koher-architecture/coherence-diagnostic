# Coherence Diagnostic — Asset Locations

**Last updated:** 13 February 2026

This folder is self-contained with all assets required to build and run the Coherence Diagnostic tool.

---

## Folder Structure

```
coherence-diagnostic/
├── CLAUDE.md                       # Configuration log and work remaining
├── ASSETS.md                       # This file
├── spec.md                         # Tool specification
├── src/
│   └── stage2_rules.py             # Stage 2 deterministic rules
└── models/
    └── deberta-coherence/          # Trained DeBERTa model (Stage 1)
```

---

## DeBERTa Model (Stage 1)

**Status:** Trained and ready (98.38% mean accuracy)
**Training date:** 11 January 2026

### Location

```
models/deberta-coherence/
```

### Files

| File | Size | Purpose |
|------|------|---------|
| `model.safetensors` | 738 MB | Trained model weights |
| `config.json` | 1.1 KB | Model configuration (DebertaV2ForSequenceClassification, 5-label) |
| `tokenizer.json` | 8.7 MB | Full tokenizer |
| `tokenizer_config.json` | 1.3 KB | Tokenizer configuration |
| `spm.model` | 2.5 MB | SentencePiece model |
| `added_tokens.json` | 23 B | Additional tokens |
| `special_tokens_map.json` | 286 B | Special token mappings |
| `training_args.bin` | 5.8 KB | Training arguments |

### Loading the Model

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = "models/deberta-coherence/"

model = AutoModelForSequenceClassification.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Inference
inputs = tokenizer(concept_text, return_tensors="pt", truncation=True, max_length=512)
outputs = model(**inputs)
confidence_scores = outputs.logits.sigmoid().tolist()[0]

# confidence_scores is [CLAIM, EVIDENCE, SCOPE, ASSUMPTIONS, GAPS]
# Each value is 0.0–1.0
```

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

## Stage 2 Rules

**Status:** Updated for float confidence scores

### Location

```
src/stage2_rules.py
```

### Usage

```python
from stage2_rules import evaluate_concept, format_severity_display

# Input: confidence scores from DeBERTa
stage1_output = {
    "CLAIM": 0.85,
    "EVIDENCE": 0.32,
    "SCOPE": 0.91,
    "ASSUMPTIONS": 0.67,
    "GAPS": 0.15
}

# Get structured evaluation
evaluation = evaluate_concept(stage1_output)

# Access severity levels for Haiku prompt
severity_levels = evaluation["severity_levels"]
# {"CLAIM": "SOLID", "EVIDENCE": "ATTENTION_NEEDED", ...}

# Format for display
print(format_severity_display(evaluation))
```

---

## Stage 3: Haiku API

**Status:** System prompt ready (in `spec.md`)
**No local assets required** — users provide their own Anthropic API key.

---

## Infrastructure Requirements

### For Development (Local)

- Python 3.10+
- PyTorch 2.0+
- transformers library
- ~4 GB RAM for model inference

### For Production (VPS)

- VPS with 4+ GB RAM
- CUDA optional (CPU inference ~500ms per concept)
- FastAPI for backend
- User-provided Anthropic API key for Haiku (Stage 3)

---

## What's NOT Included

| Item | Reason |
|------|--------|
| Training checkpoints | Not needed for inference |
| Stage 3 training data | Haiku API used; open source users provide own API key |

---

## Original Source Documents

For historical reference (in `archive/13feb/`):

| Document | Location | Purpose |
|----------|----------|---------|
| Tool 2 Spec | `archive/13feb/course-correction/tool-2-coherence-diagnostic.md` | Original authoritative specification |
| Training Results | `archive/13feb/main-codebase/design_coherence/docs/training-results.md` | Full training metrics and analysis |
| Annotation Guidelines | `archive/13feb/main-codebase/design_coherence/data/annotation-guidelines.md` | How the 5 dimensions were labelled |

---

*This folder is self-contained. All assets required to build the tool are included.*
