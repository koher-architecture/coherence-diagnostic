# Design Concept Coherence Diagnostic

**Date:** 13 February 2026
**Status:** Ready to build
**Requires:** DeBERTa model (trained, 98.38% accuracy), Stage 2 rules (needs float update), Haiku API key
**Build estimate:** 3-4 days
**Priority:** Reference implementation — demonstrates Koher architecture

---

## What This Is

A standalone tool that takes a design concept and shows what's strong, what's thin, and what's unclear. Five dimensions scored deterministically. Confidence surfaced where the model is uncertain. Plain language diagnosis generated from those scores. No exercises, no questioning, no dialogue.

A mirror. The student sees the shape of what they've written — including the parts that are too vague to read clearly.

---

## What This Is Not

- Not a grading system (no pass/fail, no score out of 10)
- Not a fix-it tool (shows problems, doesn't solve them)
- Not a dialogue partner (one-shot feedback, not conversation)
- Not a template enforcer (works on free-form text)

---

## The Broken Relationship

Design students write concepts that are vague, overreaching, or unsupported. The relationship between **what they intend** and **what they've articulated** is broken by unclear thinking expressed in unclear language.

A student writes "my project helps communities share knowledge." The supervisor reads it and cannot tell: Which communities? What knowledge? How? The concept carries intention without articulation.

**Who has this problem:** Design educators, thesis supervisors, studio instructors, anyone evaluating student concept writing.

**Why experts recognise quality:** An experienced design educator reads a concept and knows in seconds whether it holds together. They've seen thousands. They can spot what's missing before they finish reading. But they can't be everywhere.

---

## Architectural Principle

**AI handles language. Code handles judgment.**

DeBERTa (domain-trained, 98.38% accuracy) produces confidence scores — probabilities per dimension, not binary outputs. Stage 2 rules (pure Python, no AI) convert confidence into three severity levels using fixed thresholds. These are auditable, reproducible, and not subject to prompt drift.

Haiku generates language only. It receives scores and severity levels it did not produce and translates them into plain English. It never decides what's strong, weak, or unclear — that decision is already made before Haiku sees the concept.

```
                  JUDGMENT (deterministic)                    LANGUAGE (AI)
                  ───────────────────────────────────         ─────────────
Student text ──→  DeBERTa ──→ confidence ──→ Rules ──→ severity ──→ Haiku ──→ diagnosis
                  (domain)    (0.0-1.0)      (code)    (3 levels)   (API)     (streams)
```

---

## The Five Dimensions

### DIMENSION: CLAIM

**Question:** Is the core claim clearly stated?

**Polarity:** Standard (high confidence = quality present)

**Definition:** The concept contains a specific, testable assertion about what the design will achieve. A claim can be evaluated — it could be right or wrong.

**What to look for:**
- Specific statements about what the design does or achieves
- Testable assertions ("X will improve Y for Z")
- Clear statements of intention beyond description

**What signals ABSENT:**
- "My project explores..." (exploration is not a claim)
- "The design might help..." (hedged language)
- Description of features without stating purpose
- Vague intentions ("make things better")

---

### DIMENSION: EVIDENCE

**Question:** Is there adequate supporting evidence?

**Polarity:** Standard

**Definition:** The concept references observations, research, data, or prior work that supports the claim. Evidence shows why the claim might be true.

**What to look for:**
- References to user research, interviews, or observations
- Data or statistics cited
- Prior art or existing solutions mentioned
- Specific findings that support the direction

**What signals ABSENT:**
- Claims without support
- "I believe users want..." without demonstration
- Assumptions presented as facts
- No reference to investigation or research

---

### DIMENSION: SCOPE

**Question:** Is the scope appropriately bounded?

**Polarity:** Standard

**Definition:** The concept explicitly states boundaries — who it's for, where it applies, what it doesn't address. Scope makes claims manageable and testable.

**What to look for:**
- Specific user groups named ("factory workers in Tiruppur aged 25-40")
- Geographic or contextual boundaries ("urban slums in Mumbai")
- Explicit exclusions ("this does not address...")
- Conditions for applicability

**What signals ABSENT:**
- "Communities" without specifying which
- "Users" without definition
- Universal claims ("everyone needs...")
- No boundaries stated

---

### DIMENSION: ASSUMPTIONS

**Question:** Are key assumptions acknowledged?

**Polarity:** Standard

**Definition:** The concept explicitly names what must be true for the design to work — the conditions, beliefs, or prerequisites that aren't proven.

**What to look for:**
- "We assume that..." or "This requires..."
- Named dependencies ("users must have smartphone access")
- Acknowledged uncertainties
- Conditions for success stated

**What signals ABSENT:**
- Hidden prerequisites
- Unstated dependencies
- Treating assumptions as facts
- No acknowledgment of what could be wrong

---

### DIMENSION: GAPS

**Question:** Are there critical reasoning gaps?

**Polarity:** Inverted (high confidence = problem PRESENT = bad)

**Definition:** The concept contains logical jumps — steps in reasoning that are skipped, effects claimed without causal pathway, or disconnected elements.

**What to look for:**
- Logical jumps ("we'll provide X, therefore Y will happen")
- Missing causal chains
- Effects claimed without mechanism
- Disconnected problem and solution

**What signals NO gaps:**
- Clear logical flow
- Cause and effect connected
- Reasoning chain visible

---

## Confidence and Severity

DeBERTa outputs a probability per dimension: how confident the model is that the dimension is present. Vague student writing produces low-confidence scores — the model can tell it's uncertain.

### Thresholds (for CLAIM, EVIDENCE, SCOPE, ASSUMPTIONS)

| DeBERTa confidence | Severity | Meaning |
|--------------------|----------|---------|
| > 0.8 | SOLID | Model is confident the dimension is present |
| 0.5 – 0.8 | WORTH_EXAMINING | Dimension appears present but writing is vague enough that the model isn't sure |
| < 0.5 | ATTENTION_NEEDED | Dimension appears absent |

### Thresholds (for GAPS — inverted polarity)

GAPS confidence = probability that gaps ARE present. High confidence = bad.

| DeBERTa confidence | Severity | Meaning |
|--------------------|----------|---------|
| < 0.2 | SOLID | Model is confident no gaps exist |
| 0.2 – 0.5 | WORTH_EXAMINING | Model isn't sure whether gaps exist |
| > 0.5 | ATTENTION_NEEDED | Model is confident gaps are present |

### Why Three Levels

Binary scoring (present/absent) forces a false choice on vague language. A concept with CLAIM confidence 0.52 and CLAIM confidence 0.95 both register as "present" — but the first is barely legible and the second is clear. The three-level system makes the uncertain middle visible.

---

## Relationship Rules

Stage 2 applies relationship logic beyond individual dimension scoring:

```python
# CLAIM without EVIDENCE → unsupported assertion
if severity["CLAIM"] == "SOLID" and severity["EVIDENCE"] == "ATTENTION_NEEDED":
    finding = "Claim is present but unsupported — no evidence shows why it might be true"

# EVIDENCE without CLAIM → unfocused data
if severity["EVIDENCE"] == "SOLID" and severity["CLAIM"] == "ATTENTION_NEEDED":
    finding = "Evidence is present but no clear claim — data without direction"

# CLAIM and EVIDENCE both absent → foundation missing
if severity["CLAIM"] == "ATTENTION_NEEDED" and severity["EVIDENCE"] == "ATTENTION_NEEDED":
    finding = "Neither claim nor evidence present — concept lacks foundation"

# SCOPE unbounded with strong CLAIM → overreach
if severity["CLAIM"] == "SOLID" and severity["SCOPE"] == "ATTENTION_NEEDED":
    finding = "Strong claim but unbounded scope — assertion exceeds what can be tested"

# Everything present → coherent
if all(severity[dim] == "SOLID" for dim in ["CLAIM", "EVIDENCE", "SCOPE", "ASSUMPTIONS"]) \
   and severity["GAPS"] == "SOLID":
    finding = "Concept appears coherent — all dimensions present"
```

---

## User Flow

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  1. LANDING                                          │
│     Brief framing + text area                        │
│                                                      │
│  2. SUBMIT                                           │
│     Student pastes or writes concept (2-8 sentences) │
│                                                      │
│  3. SCORES (instant — <500ms)                        │
│     5 dimensions with three-state display            │
│                                                      │
│  4. DIAGNOSIS (streams — 2-4 seconds)                │
│     Plain language explanation including uncertainty  │
│                                                      │
│  5. REVISION (optional)                              │
│     "Revise and resubmit" → back to text area        │
│     Revised concept gets fresh analysis              │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Step 1: Landing

```
Paste your design concept below.

This tool checks five things: whether your claim is
clear, whether you've supported it, whether the scope
is bounded, whether assumptions are acknowledged, and
whether there are gaps in your reasoning.

It won't fix anything. It shows you the shape.

[Text area — placeholder: "Write or paste your design
 concept here (2-8 sentences)"]

                    [Analyse]
```

No login. No account. Free tier: 5 analyses per day.

---

## Step 3: Scores

Displayed immediately while diagnosis loads.

### Example: Mixed Confidence

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  YOUR CONCEPT                                        │
│  "My project creates a platform for communities      │
│  to share local knowledge and preserve cultural      │
│  heritage through collaborative storytelling."       │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  CLAIM          ◐ Unclear                            │
│  EVIDENCE       ○ Absent          ← Needs attention  │
│  SCOPE          ○ Unbounded       ← Needs attention  │
│  ASSUMPTIONS    ○ Hidden          ← Needs attention  │
│  GAPS           ● Connected                          │
│                                                      │
│  Diagnosis loading...                                │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Score Display Logic

| Severity | Symbol | Display |
|----------|--------|---------|
| SOLID | ● | `● [positive label]` — no flag |
| WORTH_EXAMINING | ◐ | `◐ Unclear` — no flag, no alarm |
| ATTENTION_NEEDED | ○ | `○ [negative label] ← Needs attention` |

### Dimension Labels (student-facing)

| Dimension | SOLID | WORTH_EXAMINING | ATTENTION_NEEDED |
|-----------|-------|-----------------|------------------|
| CLAIM | ● Present | ◐ Unclear | ○ Unclear or missing |
| EVIDENCE | ● Supported | ◐ Unclear | ○ Absent |
| SCOPE | ● Bounded | ◐ Unclear | ○ Unbounded |
| ASSUMPTIONS | ● Acknowledged | ◐ Unclear | ○ Hidden |
| GAPS | ● Connected | ◐ Unclear | ○ Gaps present |

---

## Step 4: Diagnosis

Streams below the scores as it generates.

### Example

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  WHAT THE SCORES SHOW                                │
│                                                      │
│  There's something claim-shaped in "creates a        │
│  platform for communities to share local knowledge"  │
│  — but it's broad enough that the tool can't tell    │
│  whether it's a specific intention or a general      │
│  aspiration. What exactly will this platform do that  │
│  existing ways of sharing knowledge don't?           │
│                                                      │
│  No evidence supports the direction. What have you   │
│  seen or heard that tells you communities want this  │
│  kind of platform?                                   │
│                                                      │
│  The scope is carrying more than the foundation      │
│  supports. "Communities" is everyone. "Cultural       │
│  heritage" is everything. Which community? Whose     │
│  heritage?                                           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Diagnosis Requirements

- Plain language. No jargon. No framework vocabulary.
- 3-6 sentences. Concise.
- Names what's weak and why — specifically, using the student's own words.
- For WORTH_EXAMINING dimensions: names the vagueness.
- Does not prescribe fixes. (Questions, not instructions.)
- Does not praise what's strong. (Mirror, not judge.)

---

## Stage 3: Haiku

### System Prompt

```
You are a design coherence analyst. A student has submitted
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
- Do not contradict the scores or severity levels

Concept: {text}

Severity:
- CLAIM: {SOLID/WORTH_EXAMINING/ATTENTION_NEEDED}
- EVIDENCE: {SOLID/WORTH_EXAMINING/ATTENTION_NEEDED}
- SCOPE: {SOLID/WORTH_EXAMINING/ATTENTION_NEEDED}
- ASSUMPTIONS: {SOLID/WORTH_EXAMINING/ATTENTION_NEEDED}
- GAPS: {SOLID/WORTH_EXAMINING/ATTENTION_NEEDED}

Stage 2 evaluation:
{stage2_json}
```

### Cost Analysis

**Haiku 4.5 pricing:** $1.00/MTok input, $5.00/MTok output.

| Scale | Analyses | Cost/month |
|-------|----------|------------|
| Small class (25 students × 3) | 75 | ₹6 |
| Weekly usage (100/week) | 400 | ₹32 |
| Daily usage (100/day) | 3,000 | ₹240 |
| Moderate SaaS (500/day) | 15,000 | ₹1,200 |

Haiku is cheaper than running a VPS until ~50,000 analyses/month (~1,700/day).

---

## Existing Assets

### DeBERTa Model (Stage 1) — READY

**Location:** `archive/13feb/main-codebase/design_coherence/outputs/deberta-coherence/`

| File | Size | Purpose |
|------|------|---------|
| `model.safetensors` | 738MB | Trained weights |
| `config.json` | 1.1KB | Model config |
| `tokenizer.json` | 8.7MB | Full tokenizer |
| `spm.model` | 2.5MB | SentencePiece |

**Training results (11 January 2026):**

| Dimension | Accuracy |
|-----------|----------|
| CLAIM | 97.85% |
| EVIDENCE | 98.81% |
| SCOPE | 99.28% |
| ASSUMPTIONS | 97.37% |
| GAPS | 98.57% |
| **Mean** | **98.38%** |

### Stage 2 Rules — NEEDS UPDATE

**Location:** `src/stage2_rules.py` (this folder)

**Current state:** Accepts binary 0/1 inputs
**Needs:** Accept float 0.0–1.0 inputs + apply confidence thresholds

Update scope: ~50 lines of code. Add `classify_confidence()` function.

### Training Data — AVAILABLE

**Location:** `archive/13feb/main-codebase/design_coherence/data/stage3/train_plain_diagnosis.jsonl`

**Content:** 2,000 examples of concept + scores → plain language diagnosis

Retained as fallback if Haiku becomes unavailable.

---

## What This Requires to Build

| Component | Status | Effort |
|-----------|--------|--------|
| DeBERTa model | Exists | Load and serve |
| Stage 2 rules | Exists (needs update) | 1-2 hours |
| Haiku API integration | System prompt above | 30 min |
| FastAPI backend | Not built | 1-2 days |
| Frontend (single page) | Not built | 1 day |
| Deploy to VPS (for DeBERTa) | Not configured | 0.5 days |
| **Total** | | **~3-4 days** |

---

## What to Validate

| Question | How to test |
|----------|-------------|
| Are DeBERTa confidence scores distributed usefully? | Run 20 real student concepts. Plot confidence distributions. |
| Do the thresholds (0.5 / 0.8) land correctly? | Compare Stage 2 severity to Prayas's judgment on 20 concepts. |
| Does the three-state display make sense to students? | Ask 5 students: "What does ◐ Unclear mean to you?" |
| Does the diagnosis help revision? | Compare: student revises with vs. without diagnosis. |
| Does `◐ Unclear` → `● Present` movement motivate revision? | Observe: do students who see ◐ try to sharpen their language? |

---

## What This Does Not Do

| Limitation | Accepted because |
|------------|------------------|
| No exercises | Diagnosis alone is the hypothesis |
| No mandatory gates | Students choose whether to revise |
| No data persistence | v1 is for validation |
| LLM does not judge | By design. Judgment is deterministic. |
| Thresholds are fixed | Start fixed, adjust after empirical testing |

---

*Synthesised: 13 February 2026*
*Source: tool-2-coherence-diagnostic.md (6 February 2026)*
*Architecture: Koher three-layer (classification → rules → language)*
