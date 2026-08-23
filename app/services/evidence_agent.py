"""
Evidence & Explanation Agent for RazorGuard.

Uses Gemini as a BOUNDED explanation agent.
Falls back to deterministic template-based explanations if Gemini is unavailable.

The LLM CANNOT:
- Execute financial actions
- Change risk thresholds
- Bypass policy decisions
- Override deterministic safety controls
"""

import json
import logging
from typing import Any, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def generate_risk_explanation(
    transaction: dict,
    risk_assessment: dict,
    policy_decision: dict,
) -> dict:
    """
    Generate an explanation for a risk decision.

    Tries Gemini first, falls back to deterministic explanation.

    Parameters
    ----------
    transaction : dict
        Transaction data.
    risk_assessment : dict
        Output from RiskEngine.
    policy_decision : dict
        Output from PolicyEngine.

    Returns
    -------
    dict
        explanation, evidence_summary, recommended_action, source
    """
    # Try Gemini first
    settings = get_settings()
    if settings.GEMINI_API_KEY:
        try:
            return _gemini_explanation(transaction, risk_assessment, policy_decision)
        except Exception as e:
            logger.warning("Gemini explanation failed, using deterministic: %s", e)

    # Deterministic fallback
    return _deterministic_explanation(transaction, risk_assessment, policy_decision)


def _deterministic_explanation(
    transaction: dict,
    risk_assessment: dict,
    policy_decision: dict,
) -> dict:
    """Generate explanation from signals without LLM."""
    signals = risk_assessment.get("signals", [])
    risk_score = risk_assessment.get("risk_score", 0)
    risk_level = risk_assessment.get("risk_level", "UNKNOWN")
    decision = policy_decision.get("decision", "UNKNOWN")
    txn_id = risk_assessment.get("transaction_id", "unknown")

    # Build evidence list from signals
    evidence_items = []
    for i, sig in enumerate(signals, 1):
        evidence_items.append(f"{i}. {sig.get('evidence', 'Unknown signal')}")

    if not evidence_items:
        evidence_items = ["No specific risk signals detected."]

    evidence_summary = "\n".join(evidence_items)

    # Build explanation
    if risk_level in ("HIGH", "CRITICAL"):
        explanation = (
            f"Transaction {txn_id} has been assessed as {risk_level} risk "
            f"(score: {risk_score:.2f}). "
            f"{len(signals)} risk signal(s) were detected. "
            f"Decision: {decision}."
        )
        recommended_action = (
            "Manual review recommended. Verify transaction details with the "
            "account holder before processing."
        )
    elif risk_level == "MEDIUM":
        explanation = (
            f"Transaction {txn_id} shows moderate risk indicators "
            f"(score: {risk_score:.2f}). "
            f"Enhanced monitoring is applied."
        )
        recommended_action = "Allow with enhanced monitoring. Flag for pattern analysis."
    else:
        explanation = (
            f"Transaction {txn_id} is within normal parameters "
            f"(score: {risk_score:.2f}). No significant risk detected."
        )
        recommended_action = "Allow. No action required."

    return {
        "transaction_id": txn_id,
        "explanation": explanation,
        "evidence_summary": evidence_summary,
        "evidence_items": [sig.get("evidence", "") for sig in signals],
        "recommended_action": recommended_action,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "decision": decision,
        "source": "deterministic",
    }


def _gemini_explanation(
    transaction: dict,
    risk_assessment: dict,
    policy_decision: dict,
) -> dict:
    """Generate explanation using Gemini with structured output."""
    import google.generativeai as genai
    from app.services.llm_service import _call_with_retry, _extract_json

    settings = get_settings()
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    signals = risk_assessment.get("signals", [])
    txn_id = risk_assessment.get("transaction_id", "unknown")

    prompt = f"""You are a fraud analyst reviewing a transaction risk assessment.
Based ONLY on the provided data, write a concise explanation.

DO NOT invent evidence not present in the signals.
DO NOT suggest offensive actions.
DO NOT recommend bypassing the policy decision.

Transaction:
- ID: {txn_id}
- Amount: {transaction.get('amount', 'N/A')} {transaction.get('currency', '')}
- Merchant: {transaction.get('merchant_name', 'N/A')}
- Category: {transaction.get('merchant_category', 'N/A')}

Risk Assessment:
- Score: {risk_assessment.get('risk_score', 0):.4f}
- Level: {risk_assessment.get('risk_level', 'N/A')}
- Signals: {json.dumps(signals, indent=2)}

Policy Decision: {policy_decision.get('decision', 'N/A')}

Respond with JSON:
{{
  "explanation": "2-3 sentence explanation of why this transaction was flagged",
  "evidence_summary": "Bullet points of key evidence",
  "recommended_action": "What the reviewer should do (defense-only)"
}}"""

    raw_text = _call_with_retry(model, prompt)
    if raw_text is None:
        return _deterministic_explanation(transaction, risk_assessment, policy_decision)

    try:
        parsed = _extract_json(raw_text)
        return {
            "transaction_id": txn_id,
            "explanation": parsed.get("explanation", ""),
            "evidence_summary": parsed.get("evidence_summary", ""),
            "evidence_items": [sig.get("evidence", "") for sig in signals],
            "recommended_action": parsed.get("recommended_action", ""),
            "risk_level": risk_assessment.get("risk_level"),
            "risk_score": risk_assessment.get("risk_score"),
            "decision": policy_decision.get("decision"),
            "source": "gemini",
        }
    except Exception as e:
        logger.error("Failed to parse Gemini explanation: %s", e)
        return _deterministic_explanation(transaction, risk_assessment, policy_decision)
