#!/usr/bin/env python3
"""
Stage 2: Deterministic Rules for Design Coherence

Transforms Stage 1 confidence scores into structured feedback for Stage 3.
No AI here—purely deterministic code.

Architecture:
    Stage 1 Output       Stage 2 Rules        Stage 3 Input
    ───────────────  →   Deterministic    →   Structured feedback
    [CLAIM, EVIDENCE,    logic converts       with severity levels
     SCOPE, ASSUMPTIONS, confidence to        and relationship
     GAPS]               severity             evaluations

Updated: 13 February 2026
- Now accepts float confidence scores (0.0–1.0) from DeBERTa
- Applies configurable thresholds to determine severity
- GAPS dimension has inverted polarity (high confidence = bad)

Usage:
    from stage2_rules import evaluate_concept

    stage1_output = {
        "CLAIM": 0.85,
        "EVIDENCE": 0.32,
        "SCOPE": 0.91,
        "ASSUMPTIONS": 0.67,
        "GAPS": 0.15
    }

    feedback = evaluate_concept(stage1_output)
"""

from typing import Dict, List, Any, Union


# =============================================================================
# Severity Levels
# =============================================================================

class Severity:
    """Three levels designed for student feedback (not grading)."""
    ATTENTION_NEEDED = "ATTENTION_NEEDED"  # Must address before proceeding
    WORTH_EXAMINING = "WORTH_EXAMINING"    # Good to reflect on, not blocking
    SOLID = "SOLID"                        # No issues detected


# =============================================================================
# Confidence Thresholds
# =============================================================================

# Standard polarity: high confidence = quality present
THRESHOLD_SOLID = 0.8       # > this = SOLID
THRESHOLD_EXAMINE = 0.5     # > this (and <= SOLID) = WORTH_EXAMINING
                            # <= this = ATTENTION_NEEDED

# Inverted polarity (GAPS): high confidence = problem present
GAPS_THRESHOLD_SOLID = 0.2      # < this = SOLID (no gaps)
GAPS_THRESHOLD_EXAMINE = 0.5    # < this (and >= SOLID) = WORTH_EXAMINING
                                # >= this = ATTENTION_NEEDED (gaps present)


# =============================================================================
# Confidence Classification
# =============================================================================

def classify_confidence(dimension: str, confidence: float) -> str:
    """
    Convert DeBERTa confidence score to severity level.

    Args:
        dimension: One of CLAIM, EVIDENCE, SCOPE, ASSUMPTIONS, GAPS
        confidence: Float 0.0–1.0 from DeBERTa

    Returns:
        Severity level: SOLID, WORTH_EXAMINING, or ATTENTION_NEEDED
    """
    if dimension == "GAPS":
        # Inverted polarity: high confidence = gaps present = bad
        if confidence > GAPS_THRESHOLD_EXAMINE:
            return Severity.ATTENTION_NEEDED
        elif confidence > GAPS_THRESHOLD_SOLID:
            return Severity.WORTH_EXAMINING
        else:
            return Severity.SOLID
    else:
        # Standard polarity: high confidence = dimension present = good
        if confidence > THRESHOLD_SOLID:
            return Severity.SOLID
        elif confidence > THRESHOLD_EXAMINE:
            return Severity.WORTH_EXAMINING
        else:
            return Severity.ATTENTION_NEEDED


def get_severity_map(stage1_output: Dict[str, float]) -> Dict[str, str]:
    """
    Convert all confidence scores to severity levels.

    Args:
        stage1_output: Dict with confidence scores for each dimension

    Returns:
        Dict mapping dimension names to severity levels
    """
    return {
        dim: classify_confidence(dim, conf)
        for dim, conf in stage1_output.items()
    }


# =============================================================================
# Rule 1: Claim-Evidence Relationship
# =============================================================================

def evaluate_claim_evidence(claim_severity: str, evidence_severity: str) -> Dict[str, Any]:
    """
    Evaluate the relationship between CLAIM and EVIDENCE.

    The relationship matters more than individual values:
    - A claim without evidence is an assertion
    - Evidence without a claim is unfocused data

    Args:
        claim_severity: Severity level for CLAIM
        evidence_severity: Severity level for EVIDENCE

    Returns:
        Evaluation dict with status, severity, finding, and prompts
    """
    if claim_severity == Severity.SOLID and evidence_severity == Severity.ATTENTION_NEEDED:
        return {
            "status": "CLAIM_WITHOUT_EVIDENCE",
            "severity": Severity.ATTENTION_NEEDED,
            "finding": "You've made a claim but haven't shown how you know it's true.",
            "prompts": [
                "What observation, interview, or data supports this claim?",
                "How do you know users actually need this?"
            ]
        }

    elif claim_severity == Severity.ATTENTION_NEEDED and evidence_severity == Severity.SOLID:
        return {
            "status": "EVIDENCE_WITHOUT_CLAIM",
            "severity": Severity.ATTENTION_NEEDED,
            "finding": "You've gathered evidence but haven't stated what you're claiming.",
            "prompts": [
                "What specific, testable claim does this evidence support?",
                "What will change if your design succeeds?"
            ]
        }

    elif claim_severity == Severity.ATTENTION_NEEDED and evidence_severity == Severity.ATTENTION_NEEDED:
        return {
            "status": "FOUNDATION_MISSING",
            "severity": Severity.ATTENTION_NEEDED,
            "finding": "Neither a clear claim nor supporting evidence is present.",
            "prompts": [
                "What specifically will your design achieve?",
                "How will you know if it worked?"
            ]
        }

    elif claim_severity == Severity.WORTH_EXAMINING or evidence_severity == Severity.WORTH_EXAMINING:
        # At least one is unclear
        return {
            "status": "CLAIM_EVIDENCE_UNCLEAR",
            "severity": Severity.WORTH_EXAMINING,
            "finding": "Claim and evidence relationship is unclear — one or both are vague.",
            "prompts": [
                "Can you state your claim more specifically?",
                "What concrete evidence supports this direction?"
            ]
        }

    else:  # Both SOLID
        return {
            "status": "CLAIM_EVIDENCE_ALIGNED",
            "severity": Severity.SOLID,
            "finding": "Claim is stated and evidence is present.",
            "prompts": []
        }


# =============================================================================
# Rule 2: Scope Evaluation
# =============================================================================

def evaluate_scope(scope_severity: str) -> Dict[str, Any]:
    """
    Evaluate whether scope is appropriately bounded.

    Args:
        scope_severity: Severity level for SCOPE

    Returns:
        Evaluation dict with status, severity, finding, and prompts
    """
    if scope_severity == Severity.ATTENTION_NEEDED:
        return {
            "status": "SCOPE_UNBOUNDED",
            "severity": Severity.ATTENTION_NEEDED,
            "finding": "The scope is unbounded or unstated.",
            "prompts": [
                "Who specifically is this for?",
                "What are the boundaries of your design context?"
            ]
        }
    elif scope_severity == Severity.WORTH_EXAMINING:
        return {
            "status": "SCOPE_UNCLEAR",
            "severity": Severity.WORTH_EXAMINING,
            "finding": "Scope is mentioned but vague — boundaries aren't clear.",
            "prompts": [
                "Can you be more specific about who this is for?",
                "Where does this apply, and where doesn't it?"
            ]
        }
    else:
        return {
            "status": "SCOPE_BOUNDED",
            "severity": Severity.SOLID,
            "finding": "Scope is explicitly stated.",
            "prompts": []
        }


# =============================================================================
# Rule 3: Assumptions Evaluation
# =============================================================================

def evaluate_assumptions(assumptions_severity: str) -> Dict[str, Any]:
    """
    Evaluate whether key assumptions are acknowledged.

    Note: Even when assumptions are acknowledged (good), we still suggest
    examining them. The prompts help deepen reflection without suggesting
    something is wrong.

    Args:
        assumptions_severity: Severity level for ASSUMPTIONS

    Returns:
        Evaluation dict with status, severity, finding, and prompts
    """
    if assumptions_severity == Severity.ATTENTION_NEEDED:
        return {
            "status": "ASSUMPTIONS_HIDDEN",
            "severity": Severity.ATTENTION_NEEDED,
            "finding": "Key assumptions are not acknowledged.",
            "prompts": [
                "What are you assuming about your users?",
                "What must be true for your design to work?",
                "Which assumption are you least sure about?"
            ]
        }
    elif assumptions_severity == Severity.WORTH_EXAMINING:
        return {
            "status": "ASSUMPTIONS_UNCLEAR",
            "severity": Severity.WORTH_EXAMINING,
            "finding": "Some assumptions mentioned but not clearly stated.",
            "prompts": [
                "Can you state your assumptions more explicitly?",
                "What would prove your assumptions wrong?"
            ]
        }
    else:
        return {
            "status": "ASSUMPTIONS_ACKNOWLEDGED",
            "severity": Severity.WORTH_EXAMINING,  # Always worth examining
            "finding": "Assumptions are acknowledged—worth examining them.",
            "prompts": [
                "How confident are you in each assumption?",
                "What would prove your assumptions wrong?"
            ]
        }


# =============================================================================
# Rule 4: Gaps Evaluation
# =============================================================================

def evaluate_gaps(gaps_severity: str) -> Dict[str, Any]:
    """
    Evaluate whether there are critical reasoning gaps.

    Note: For GAPS, the severity has already been computed with inverted
    polarity (high confidence = gaps present = ATTENTION_NEEDED).

    Args:
        gaps_severity: Severity level for GAPS (already inverted)

    Returns:
        Evaluation dict with status, severity, finding, and prompts
    """
    if gaps_severity == Severity.ATTENTION_NEEDED:  # Gaps present (bad)
        return {
            "status": "REASONING_GAPS_PRESENT",
            "severity": Severity.ATTENTION_NEEDED,
            "finding": "There are logical jumps in the reasoning.",
            "prompts": [
                "What connects your research findings to this specific solution?",
                "How does the problem lead to your proposed design?"
            ]
        }
    elif gaps_severity == Severity.WORTH_EXAMINING:
        return {
            "status": "REASONING_GAPS_UNCLEAR",
            "severity": Severity.WORTH_EXAMINING,
            "finding": "Some reasoning connections are unclear.",
            "prompts": [
                "Can you make the logical steps more explicit?",
                "What's the causal chain from problem to solution?"
            ]
        }
    else:  # SOLID = no gaps
        return {
            "status": "REASONING_CONNECTED",
            "severity": Severity.SOLID,
            "finding": "Reasoning chain is connected.",
            "prompts": []
        }


# =============================================================================
# Combined Evaluation
# =============================================================================

def evaluate_concept(stage1_output: Dict[str, Union[int, float]]) -> Dict[str, Any]:
    """
    Main Stage 2 function.

    Takes Stage 1 outputs (confidence scores or binary), returns structured
    feedback for Stage 3.

    Args:
        stage1_output: Dict with keys CLAIM, EVIDENCE, SCOPE, ASSUMPTIONS, GAPS
                       Each value is 0.0–1.0 (confidence) or 0/1 (legacy binary)

    Returns:
        Structured evaluation with:
        - claim_evidence: Combined evaluation of claim and evidence
        - scope: Scope evaluation
        - assumptions: Assumptions evaluation
        - gaps: Gaps evaluation
        - severity_levels: The severity level for each dimension
        - summary: Overall status and counts

    Example:
        >>> evaluate_concept({"CLAIM": 0.85, "EVIDENCE": 0.32, "SCOPE": 0.91,
        ...                   "ASSUMPTIONS": 0.67, "GAPS": 0.15})
        {
            "claim_evidence": {"status": "CLAIM_WITHOUT_EVIDENCE", ...},
            "scope": {"status": "SCOPE_BOUNDED", ...},
            "severity_levels": {"CLAIM": "SOLID", "EVIDENCE": "ATTENTION_NEEDED", ...},
            ...
        }
    """
    # Convert confidence to severity (handles both float and legacy binary)
    severity = get_severity_map(stage1_output)

    evaluation = {
        "claim_evidence": evaluate_claim_evidence(severity["CLAIM"], severity["EVIDENCE"]),
        "scope": evaluate_scope(severity["SCOPE"]),
        "assumptions": evaluate_assumptions(severity["ASSUMPTIONS"]),
        "gaps": evaluate_gaps(severity["GAPS"]),
        "severity_levels": severity,
        "confidence_scores": stage1_output
    }

    # Compute summary
    attention_count = sum(
        1 for e in [evaluation["claim_evidence"], evaluation["scope"],
                    evaluation["assumptions"], evaluation["gaps"]]
        if e["severity"] == Severity.ATTENTION_NEEDED
    )
    examine_count = sum(
        1 for e in [evaluation["claim_evidence"], evaluation["scope"],
                    evaluation["assumptions"], evaluation["gaps"]]
        if e["severity"] == Severity.WORTH_EXAMINING
    )
    solid_count = sum(
        1 for e in [evaluation["claim_evidence"], evaluation["scope"],
                    evaluation["assumptions"], evaluation["gaps"]]
        if e["severity"] == Severity.SOLID
    )

    evaluation["summary"] = {
        "attention_count": attention_count,
        "examine_count": examine_count,
        "solid_count": solid_count,
        "total_dimensions": 4,
        "overall_status": "NEEDS_WORK" if attention_count > 0 else "COHERENT"
    }

    return evaluation


# =============================================================================
# Convenience Functions
# =============================================================================

def get_all_prompts(evaluation: Dict[str, Any]) -> List[str]:
    """
    Extract all prompts from an evaluation result.

    Args:
        evaluation: Result from evaluate_concept()

    Returns:
        List of all prompt strings across all dimensions
    """
    prompts = []
    for key in ["claim_evidence", "scope", "assumptions", "gaps"]:
        prompts.extend(evaluation[key]["prompts"])
    return prompts


def get_attention_items(evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get only items that need attention.

    Args:
        evaluation: Result from evaluate_concept()

    Returns:
        List of evaluation dicts where severity is ATTENTION_NEEDED
    """
    items = []
    for key in ["claim_evidence", "scope", "assumptions", "gaps"]:
        if evaluation[key]["severity"] == Severity.ATTENTION_NEEDED:
            items.append({
                "dimension": key,
                **evaluation[key]
            })
    return items


def format_feedback(evaluation: Dict[str, Any]) -> str:
    """
    Format evaluation as human-readable feedback.

    Args:
        evaluation: Result from evaluate_concept()

    Returns:
        Formatted string with findings and prompts
    """
    lines = []

    summary = evaluation["summary"]
    if summary["overall_status"] == "COHERENT":
        lines.append("Overall: COHERENT")
        lines.append("")
    else:
        lines.append(f"Overall: NEEDS WORK ({summary['attention_count']} areas need attention)")
        lines.append("")

    for key in ["claim_evidence", "scope", "assumptions", "gaps"]:
        item = evaluation[key]
        severity_marker = {
            Severity.ATTENTION_NEEDED: "○",
            Severity.WORTH_EXAMINING: "◐",
            Severity.SOLID: "●"
        }.get(item["severity"], "")

        lines.append(f"{severity_marker} {key.upper()}: {item['status']}")
        lines.append(f"   {item['finding']}")

        if item["prompts"]:
            for prompt in item["prompts"]:
                lines.append(f"   → {prompt}")
        lines.append("")

    return "\n".join(lines)


def format_severity_display(evaluation: Dict[str, Any]) -> str:
    """
    Format severity levels for UI display (three-state symbols).

    Args:
        evaluation: Result from evaluate_concept()

    Returns:
        Formatted string with dimension scores
    """
    severity = evaluation["severity_levels"]
    labels = {
        "CLAIM": {"SOLID": "● Present", "WORTH_EXAMINING": "◐ Unclear", "ATTENTION_NEEDED": "○ Unclear or missing"},
        "EVIDENCE": {"SOLID": "● Supported", "WORTH_EXAMINING": "◐ Unclear", "ATTENTION_NEEDED": "○ Absent"},
        "SCOPE": {"SOLID": "● Bounded", "WORTH_EXAMINING": "◐ Unclear", "ATTENTION_NEEDED": "○ Unbounded"},
        "ASSUMPTIONS": {"SOLID": "● Acknowledged", "WORTH_EXAMINING": "◐ Unclear", "ATTENTION_NEEDED": "○ Hidden"},
        "GAPS": {"SOLID": "● Connected", "WORTH_EXAMINING": "◐ Unclear", "ATTENTION_NEEDED": "○ Gaps present"}
    }

    lines = []
    for dim in ["CLAIM", "EVIDENCE", "SCOPE", "ASSUMPTIONS", "GAPS"]:
        sev = severity[dim]
        label = labels[dim][sev]
        flag = " ← Needs attention" if sev == Severity.ATTENTION_NEEDED else ""
        lines.append(f"{dim:12} {label}{flag}")

    return "\n".join(lines)


# =============================================================================
# Testing
# =============================================================================

def test_confidence_thresholds():
    """
    Test that confidence thresholds work correctly.
    """
    # Standard polarity tests
    assert classify_confidence("CLAIM", 0.95) == Severity.SOLID
    assert classify_confidence("CLAIM", 0.75) == Severity.WORTH_EXAMINING
    assert classify_confidence("CLAIM", 0.35) == Severity.ATTENTION_NEEDED

    # Boundary tests
    assert classify_confidence("EVIDENCE", 0.81) == Severity.SOLID
    assert classify_confidence("EVIDENCE", 0.80) == Severity.WORTH_EXAMINING
    assert classify_confidence("EVIDENCE", 0.51) == Severity.WORTH_EXAMINING
    assert classify_confidence("EVIDENCE", 0.50) == Severity.ATTENTION_NEEDED

    # Inverted polarity (GAPS)
    assert classify_confidence("GAPS", 0.15) == Severity.SOLID  # Low = good
    assert classify_confidence("GAPS", 0.35) == Severity.WORTH_EXAMINING
    assert classify_confidence("GAPS", 0.60) == Severity.ATTENTION_NEEDED  # High = bad

    print("✓ Confidence threshold tests passed")


def test_full_evaluation():
    """
    Test full evaluation pipeline with confidence scores.
    """
    # Example: Strong claim, weak evidence, bounded scope
    result = evaluate_concept({
        "CLAIM": 0.92,
        "EVIDENCE": 0.28,
        "SCOPE": 0.85,
        "ASSUMPTIONS": 0.65,
        "GAPS": 0.12
    })

    assert result["claim_evidence"]["status"] == "CLAIM_WITHOUT_EVIDENCE"
    assert result["scope"]["severity"] == Severity.SOLID
    assert result["assumptions"]["severity"] == Severity.WORTH_EXAMINING
    assert result["gaps"]["severity"] == Severity.SOLID

    print("✓ Full evaluation test passed")


def test_all_states():
    """
    Test representative confidence combinations.
    """
    test_cases = [
        # Strong across the board
        {"CLAIM": 0.95, "EVIDENCE": 0.90, "SCOPE": 0.88, "ASSUMPTIONS": 0.85, "GAPS": 0.10},
        # Weak across the board
        {"CLAIM": 0.25, "EVIDENCE": 0.30, "SCOPE": 0.20, "ASSUMPTIONS": 0.15, "GAPS": 0.70},
        # Mixed
        {"CLAIM": 0.65, "EVIDENCE": 0.45, "SCOPE": 0.90, "ASSUMPTIONS": 0.55, "GAPS": 0.35},
        # Claim without evidence
        {"CLAIM": 0.92, "EVIDENCE": 0.22, "SCOPE": 0.85, "ASSUMPTIONS": 0.75, "GAPS": 0.15},
        # Evidence without claim
        {"CLAIM": 0.30, "EVIDENCE": 0.88, "SCOPE": 0.75, "ASSUMPTIONS": 0.60, "GAPS": 0.20},
    ]

    for i, tc in enumerate(test_cases):
        result = evaluate_concept(tc)

        # Verify structure
        assert "summary" in result
        assert "severity_levels" in result
        assert result["summary"]["attention_count"] >= 0
        assert result["summary"]["attention_count"] <= 4
        assert result["summary"]["overall_status"] in ["NEEDS_WORK", "COHERENT"]

        # Verify all dimensions present
        for key in ["claim_evidence", "scope", "assumptions", "gaps"]:
            assert key in result
            assert "status" in result[key]
            assert "severity" in result[key]
            assert "finding" in result[key]
            assert "prompts" in result[key]

    print(f"✓ All {len(test_cases)} test cases passed")
    return True


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import json

    print("Stage 2: Deterministic Rules (Float Confidence)")
    print("=" * 50)
    print()

    # Run tests
    print("Running tests...")
    test_confidence_thresholds()
    test_full_evaluation()
    test_all_states()
    print()

    # Example evaluation with confidence scores
    print("Example evaluation:")
    print("-" * 50)

    example_input = {
        "CLAIM": 0.62,       # Unclear (something claim-shaped but vague)
        "EVIDENCE": 0.28,    # Absent
        "SCOPE": 0.35,       # Unbounded
        "ASSUMPTIONS": 0.42, # Hidden
        "GAPS": 0.18         # Connected (no gaps)
    }

    print(f"Input confidence scores: {json.dumps(example_input, indent=2)}")
    print()

    result = evaluate_concept(example_input)

    print("Severity Display:")
    print(format_severity_display(result))
    print()

    print("Full Feedback:")
    print(format_feedback(result))

    print("-" * 50)
    print("Raw output:")
    print(json.dumps(result, indent=2, default=str))
