"""
LLM service using Google Gemini 1.5 Flash.

Provides batch transaction classification and narrative summary generation.
Handles missing API keys gracefully and includes retry logic with exponential
backoff.
"""

import json
import logging
import time
from typing import Any

import google.generativeai as genai

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES: int = 3
_BACKOFF_SECONDS: list[int] = [1, 2, 4]

_VALID_CATEGORIES: set[str] = {
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other",
}


def _get_model() -> genai.GenerativeModel | None:
    """Configure the Gemini SDK and return a model instance, or None if no key."""
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set – LLM features disabled")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def _call_with_retry(model: genai.GenerativeModel, prompt: str) -> str | None:
    """Send a prompt to Gemini with retry logic. Returns raw text or None."""
    for attempt in range(_MAX_RETRIES):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as exc:
            wait = _BACKOFF_SECONDS[attempt] if attempt < len(_BACKOFF_SECONDS) else 4
            logger.warning(
                "Gemini call failed (attempt %d/%d): %s – retrying in %ds",
                attempt + 1,
                _MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    logger.error("All %d Gemini retries exhausted", _MAX_RETRIES)
    return None


def _extract_json(raw_text: str) -> Any:
    """Extract a JSON array or object from the model's response text."""
    # The model may wrap JSON in markdown code fences
    text = raw_text.strip()
    if text.startswith("```"):
        # Remove opening fence (possibly ```json)
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
        # Remove closing fence
        if text.endswith("```"):
            text = text[: -3]
    text = text.strip()
    return json.loads(text)


# ── Public API ───────────────────────────────────────────────────────────────


def classify_transactions_batch(
    transactions: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Classify a batch of transactions into spending categories using Gemini.

    Parameters
    ----------
    transactions : list[dict]
        Each dict has keys ``merchant`` and ``notes``.

    Returns
    -------
    list[dict]
        Each dict has ``merchant``, ``notes``, ``category``, and
        ``raw_response`` (the full LLM text for debugging).
        On failure the list will mark ``category`` as ``"Other"`` and
        ``llm_failed`` as True.
    """
    if not transactions:
        return []

    model = _get_model()
    if model is None:
        # No API key – mark all as failed
        return [
            {
                "merchant": t["merchant"],
                "notes": t.get("notes", ""),
                "category": "Other",
                "raw_response": None,
                "llm_failed": True,
            }
            for t in transactions
        ]

    prompt = (
        "You are a financial transaction classifier. "
        "Classify each transaction into EXACTLY one of these categories:\n"
        "Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other\n\n"
        "Respond ONLY with a JSON array where each element has keys "
        '"merchant", "notes", "category".\n\n'
        "Transactions to classify:\n"
        f"{json.dumps(transactions, indent=2)}\n"
    )

    raw_text = _call_with_retry(model, prompt)
    if raw_text is None:
        logger.error("LLM classification failed after retries")
        return [
            {
                "merchant": t["merchant"],
                "notes": t.get("notes", ""),
                "category": "Other",
                "raw_response": None,
                "llm_failed": True,
            }
            for t in transactions
        ]

    try:
        parsed: list[dict[str, str]] = _extract_json(raw_text)
        # Validate and normalise categories
        result: list[dict[str, str]] = []
        for i, item in enumerate(parsed):
            category = item.get("category", "Other")
            if category not in _VALID_CATEGORIES:
                category = "Other"
            result.append(
                {
                    "merchant": item.get("merchant", transactions[i]["merchant"]),
                    "notes": item.get("notes", transactions[i].get("notes", "")),
                    "category": category,
                    "raw_response": raw_text,
                    "llm_failed": False,
                }
            )
        return result
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.error("Failed to parse LLM classification response: %s", exc)
        return [
            {
                "merchant": t["merchant"],
                "notes": t.get("notes", ""),
                "category": "Other",
                "raw_response": raw_text,
                "llm_failed": True,
            }
            for t in transactions
        ]


def generate_summary(transactions_data: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a narrative summary and risk assessment for a set of transactions.

    Parameters
    ----------
    transactions_data : dict
        Aggregated data including total_spend_by_currency, top_merchants,
        anomaly_count, total_transactions, etc.

    Returns
    -------
    dict
        Keys: total_spend_by_currency, top_3_merchants, anomaly_count,
        narrative, risk_level.  On failure, narrative will be a default
        string and risk_level will be derived from anomaly_count.
    """
    anomaly_count: int = transactions_data.get("anomaly_count", 0)

    # Determine risk level from anomaly count
    if anomaly_count == 0:
        risk_level = "LOW"
    elif anomaly_count <= 5:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    default_result: dict[str, Any] = {
        "total_spend_by_currency": transactions_data.get("total_spend_by_currency", {}),
        "top_3_merchants": transactions_data.get("top_merchants", []),
        "anomaly_count": anomaly_count,
        "narrative": "Summary generation unavailable.",
        "risk_level": risk_level,
    }

    model = _get_model()
    if model is None:
        return default_result

    prompt = (
        "You are a financial analyst. Based on the following transaction data, "
        "write a concise narrative summary (3-5 sentences) covering:\n"
        "1. Overall spending patterns\n"
        "2. Notable merchants\n"
        "3. Anomalies detected and risk assessment\n\n"
        "Respond ONLY with a JSON object with these keys:\n"
        '"narrative" (string), "risk_level" (one of LOW, MEDIUM, HIGH)\n\n'
        f"Transaction Data:\n{json.dumps(transactions_data, indent=2, default=str)}\n"
    )

    raw_text = _call_with_retry(model, prompt)
    if raw_text is None:
        return default_result

    try:
        parsed: dict[str, Any] = _extract_json(raw_text)
        return {
            "total_spend_by_currency": transactions_data.get("total_spend_by_currency", {}),
            "top_3_merchants": transactions_data.get("top_merchants", []),
            "anomaly_count": anomaly_count,
            "narrative": parsed.get("narrative", "Summary generation unavailable."),
            "risk_level": parsed.get("risk_level", risk_level),
        }
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Failed to parse LLM summary response: %s", exc)
        return default_result
