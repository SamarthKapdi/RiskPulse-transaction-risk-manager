"""
Risk API router for RiskPulse.

Exposes endpoints for transaction risk analysis, explanations,
evaluation metrics, and audit trail.
"""

import json
import logging
import os
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.risk_audit import RiskAuditTrail

from app.schemas.risk import (
    AuditRecord,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    EvaluationMetrics,
    RiskExplanation,
    RiskMetrics,
    RiskResult,
    RiskSignalOut,
    RiskTransactionSummary,
    TransactionAnalysisRequest,
)
from app.services.evidence_agent import generate_risk_explanation
from app.services.policy_engine import get_policy_engine
from app.services.risk_engine import get_risk_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])

# In-memory audit trail (in production, this would be in the database)
_audit_trail: dict[str, dict] = {}
_analyzed_results: dict[str, dict] = {}
_explanations: dict[str, dict] = {}


def _normalized_signals(signals: list[dict] | None) -> list[dict]:
    """Normalize legacy mojibake while preserving persisted signal meaning."""
    normalized = []
    for signal in signals or []:
        item = dict(signal)
        if isinstance(item.get("evidence"), str):
            item["evidence"] = (
                item["evidence"]
                .replace("\u00c3\u0097", chr(0x00d7))
                .replace("\u00cf\u0083", chr(0x03c3))
                .replace("\u00c3\u2014", chr(0x00d7))
                .replace("\u00cf\u0192", chr(0x03c3))
                .replace("\u00c3\u0083\u00e2\u0080\u0094", chr(0x00d7))
                .replace("\u00c3\u008f\u00c6\u0092", chr(0x03c3))
            )
        normalized.append(item)
    return normalized


def _analyze_single(txn_data: dict, db: Session) -> tuple[dict, dict, dict]:
    """Run full analysis pipeline on a single transaction."""
    engine = get_risk_engine()
    policy = get_policy_engine()
    
    txn_id = txn_data["transaction_id"]

    # Risk assessment
    risk_result = engine.analyze_transaction(txn_data)

    # Policy decision
    policy_decision = policy.evaluate(risk_result)

    # Store audit record to PostgreSQL
    audit_record = RiskAuditTrail(
        transaction_id=txn_id,
        model_version=risk_result["model_version"],
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        decision=policy_decision.decision,
        requires_review=policy_decision.requires_review,
        signals=risk_result["signals"],
        policy_version=policy_decision.policy_version,
    )
    db.add(audit_record)
    db.commit()
    db.refresh(audit_record)
    
    # Store for explanation fallback / dashboard usage if needed
    _audit_trail[txn_id] = {
        "transaction_id": txn_id,
        "timestamp": risk_result["timestamp"],
        "model_version": risk_result["model_version"],
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_result["risk_level"],
        "decision": policy_decision.decision,
        "signals": risk_result["signals"],
        "policy_version": policy_decision.policy_version,
    }

    # Combined result
    combined = {
        **risk_result,
        "decision": policy_decision.decision,
        "action_details": policy_decision.action_details,
        "requires_review": policy_decision.requires_review,
        "policy_version": policy_decision.policy_version,
    }
    _analyzed_results[txn_id] = combined

    return combined, risk_result, policy_decision.to_dict()


def _result_from_audit(record: RiskAuditTrail) -> dict:
    """Rebuild the public result shape when the process cache is cold."""
    policy_decision = get_policy_engine().evaluate({
        "risk_level": record.risk_level,
        "risk_score": record.risk_score,
    })
    signals = _normalized_signals(record.signals)
    return {
        "transaction_id": record.transaction_id,
        "risk_score": record.risk_score,
        "risk_level": record.risk_level,
        "confidence": round(max(record.risk_score, 1 - record.risk_score), 4),
        "model_version": record.model_version,
        "signals": signals,
        "signal_count": len(signals),
        "timestamp": record.timestamp.isoformat() if record.timestamp else "",
        "decision": policy_decision.decision,
        "action_details": policy_decision.action_details,
        "requires_review": record.requires_review,
        "policy_version": record.policy_version,
    }


# â”€â”€ POST /risk/analyze â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post(
    "/analyze",
    response_model=RiskResult,
    status_code=status.HTTP_200_OK,
    summary="Analyze a single transaction for risk",
    description="Submit a transaction for risk assessment. Returns risk score, "
                "level, decision, and interpretable risk signals.",
)
def analyze_transaction(
    request: TransactionAnalysisRequest,
    db: Session = Depends(get_db),
) -> RiskResult:
    """Perform risk analysis on a single transaction."""
    txn_data = request.model_dump()

    # Generate transaction ID if not provided
    if not txn_data.get("transaction_id"):
        import uuid
        txn_data["transaction_id"] = f"TXN_{uuid.uuid4().hex[:8].upper()}"

    combined, _, _ = _analyze_single(txn_data, db)
    return RiskResult(**combined)


@router.get(
    "/transactions",
    response_model=list[RiskTransactionSummary],
    summary="List persisted analyzed transactions",
)
def list_transactions(db: Session = Depends(get_db)) -> list[RiskTransactionSummary]:
    """Return historical risk decisions from the PostgreSQL audit trail."""
    records = db.query(RiskAuditTrail).order_by(
        RiskAuditTrail.timestamp.desc(),
        RiskAuditTrail.transaction_id.desc(),
    ).all()

    return [
        RiskTransactionSummary(
            transaction_id=record.transaction_id,
            timestamp=record.timestamp.isoformat() if record.timestamp else "",
            risk_score=record.risk_score,
            risk_level=record.risk_level,
            decision=record.decision,
            requires_review=record.requires_review,
            signals=_normalized_signals(record.signals),
            signal_count=len(record.signals or []),
            model_version=record.model_version,
            policy_version=record.policy_version,
        )
        for record in records
    ]


# â”€â”€ GET /risk/{transaction_id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/{transaction_id}",
    response_model=RiskResult,
    summary="Get risk result for a transaction",
)
def get_risk_result(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> RiskResult:
    """Retrieve the risk assessment for a previously analyzed transaction."""
    result = _analyzed_results.get(transaction_id)
    if result is None:
        record = db.query(RiskAuditTrail).filter(
            RiskAuditTrail.transaction_id == transaction_id
        ).first()
        if record:
            result = _result_from_audit(record)
            _analyzed_results[transaction_id] = result

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No risk analysis found for transaction {transaction_id}",
        )
    return RiskResult(**result)


# â”€â”€ GET /risk/{transaction_id}/explanation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/{transaction_id}/explanation",
    response_model=RiskExplanation,
    summary="Get explanation for a risk decision",
    description="Returns a human-readable explanation of why a transaction was "
                "flagged, with evidence grounded in model outputs and signals.",
)
def get_explanation(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> RiskExplanation:
    """Get explanation for a risk decision."""
    result = _analyzed_results.get(transaction_id)
    if result is None:
        record = db.query(RiskAuditTrail).filter(
            RiskAuditTrail.transaction_id == transaction_id
        ).first()
        if record:
            result = _result_from_audit(record)
            _analyzed_results[transaction_id] = result

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No risk analysis found for transaction {transaction_id}",
        )

    # Check cache
    if transaction_id in _explanations:
        return RiskExplanation(**_explanations[transaction_id])

    audit = _audit_trail.get(transaction_id, {})

    explanation = generate_risk_explanation(
        transaction=result,
        risk_assessment=result,
        policy_decision={"decision": result["decision"]},
    )

    _explanations[transaction_id] = explanation
    audit["explanation"] = explanation.get("explanation", "")
    return RiskExplanation(**explanation)


# â”€â”€ POST /risk/batch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post(
    "/batch",
    response_model=BatchAnalysisResponse,
    summary="Batch analyze transactions",
    description="Submit multiple transactions for risk analysis.",
)
def batch_analyze(
    request: BatchAnalysisRequest,
    db: Session = Depends(get_db),
) -> BatchAnalysisResponse:
    """Analyze a batch of transactions."""
    results = []
    for txn_req in request.transactions:
        txn_data = txn_req.model_dump()
        if not txn_data.get("transaction_id"):
            import uuid
            txn_data["transaction_id"] = f"TXN_{uuid.uuid4().hex[:8].upper()}"
        combined, _, _ = _analyze_single(txn_data, db)
        results.append(RiskResult(**combined))

    high_risk = sum(1 for r in results if r.risk_level in ("HIGH", "CRITICAL"))
    review_required = sum(1 for r in results if r.requires_review)

    return BatchAnalysisResponse(
        results=results,
        total=len(results),
        high_risk_count=high_risk,
        review_required_count=review_required,
    )


# â”€â”€ GET /risk/evaluation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/evaluation/metrics",
    response_model=EvaluationMetrics,
    summary="Get model evaluation metrics",
    description="Returns precision, recall, F1, PR-AUC, ROC-AUC, confusion matrix, "
                "and cost analysis from the held-out test set evaluation.",
)
def get_evaluation_metrics() -> EvaluationMetrics:
    """Return evaluation metrics from the held-out test set."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    report_path = os.path.join(project_root, "evaluation", "evaluation_report.json")

    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation report not found. Run ml/evaluate.py first.",
        )

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    return EvaluationMetrics(
        model=report.get("model", "unknown"),
        threshold=report.get("threshold", 0.5),
        precision=report["metrics"]["precision"],
        recall=report["metrics"]["recall"],
        f1=report["metrics"]["f1"],
        pr_auc=report["metrics"]["pr_auc"],
        roc_auc=report["metrics"]["roc_auc"],
        false_positive_rate=report["metrics"]["false_positive_rate"],
        false_negative_rate=report["metrics"]["false_negative_rate"],
        confusion_matrix=report["confusion_matrix"],
        cost_analysis=report.get("cost_analysis", {}),
        dataset=report.get("dataset", {}),
    )


# â”€â”€ GET /risk/metrics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/metrics/summary",
    response_model=RiskMetrics,
    summary="Get aggregate risk metrics",
)
def get_risk_metrics(db: Session = Depends(get_db)) -> RiskMetrics:
    """Return aggregate metrics from analyzed transactions."""
    engine = get_risk_engine()

    risk_dist = defaultdict(int)
    decision_dist = defaultdict(int)
    total_score = 0.0

    records = db.query(RiskAuditTrail).all()
    for record in records:
        risk_dist[record.risk_level] += 1
        decision_dist[record.decision] += 1
        total_score += record.risk_score

    total = len(records)
    review_queue = sum(1 for record in records if record.requires_review)

    return RiskMetrics(
        total_analyzed=total,
        risk_distribution=dict(risk_dist),
        decision_distribution=dict(decision_dist),
        review_queue_size=review_queue,
        avg_risk_score=round(total_score / total, 4) if total > 0 else 0.0,
        model_version=engine.model_version,
    )


# â”€â”€ GET /risk/audit/{transaction_id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/audit/{transaction_id}",
    response_model=AuditRecord,
    summary="Get audit trail for a transaction",
    description="Returns the full audit record for a risk decision, including "
                "model version, signals, and policy version.",
)
def get_audit_record(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> AuditRecord:
    """Get the audit trail for a specific transaction."""
    record = db.query(RiskAuditTrail).filter(RiskAuditTrail.transaction_id == transaction_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit record found for transaction {transaction_id}",
        )
    
    return AuditRecord(
        transaction_id=record.transaction_id,
        timestamp=record.timestamp.isoformat() if record.timestamp else "",
        model_version=record.model_version,
        risk_score=record.risk_score,
        risk_level=record.risk_level,
        decision=record.decision,
        requires_review=record.requires_review,
        signals=_normalized_signals(record.signals),
        policy_version=record.policy_version,
        explanation=record.explanation,
    )

