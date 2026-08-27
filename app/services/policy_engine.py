"""
Bounded Policy Engine for RiskPulse.

Deterministic decision engine that maps risk levels to actions.
The LLM CANNOT override the policy engine.

Decisions:
- LOW    â†’ ALLOW
- MEDIUM â†’ ALLOW + MONITOR
- HIGH   â†’ REVIEW
- CRITICAL â†’ HOLD

This is strictly defense-only. No offensive capabilities.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

POLICY_VERSION = "1.0.0"


@dataclass
class PolicyDecision:
    """Result of the policy engine evaluation."""
    decision: str
    risk_level: str
    risk_score: float
    action_details: str
    policy_version: str
    requires_review: bool
    defense_only: bool = True  # Always True â€” hard constraint

    def to_dict(self) -> dict:
        return asdict(self)


class PolicyEngine:
    """
    Deterministic policy engine for risk-based decision making.

    INVARIANTS:
    - Decisions are deterministic given risk level
    - LLM cannot override decisions
    - Only defense-oriented actions (detect, flag, review, hold)
    - All decisions are auditable
    """

    def __init__(self, policy_version: str = POLICY_VERSION):
        self.policy_version = policy_version

        # Decision matrix: risk_level â†’ (decision, requires_review, action_details)
        self._decision_matrix = {
            "LOW": (
                "ALLOW",
                False,
                "Transaction approved. No risk signals detected.",
            ),
            "MEDIUM": (
                "ALLOW_MONITOR",
                False,
                "Transaction approved with enhanced monitoring. "
                "Minor risk signals detected but within acceptable bounds.",
            ),
            "HIGH": (
                "REVIEW",
                True,
                "Transaction flagged for manual review. "
                "Significant risk indicators detected. Hold pending review.",
            ),
            "CRITICAL": (
                "HOLD",
                True,
                "Transaction held for immediate investigation. "
                "Critical risk indicators detected. Requires urgent review.",
            ),
        }

    def evaluate(self, risk_assessment: dict) -> PolicyDecision:
        """
        Apply policy rules to a risk assessment.

        Parameters
        ----------
        risk_assessment : dict
            Output from RiskEngine.analyze_transaction().

        Returns
        -------
        PolicyDecision
            The deterministic policy decision.
        """
        risk_level = risk_assessment.get("risk_level", "LOW")
        risk_score = risk_assessment.get("risk_score", 0.0)

        if risk_level not in self._decision_matrix:
            logger.warning("Unknown risk level '%s', defaulting to REVIEW", risk_level)
            risk_level = "HIGH"

        decision, requires_review, details = self._decision_matrix[risk_level]

        return PolicyDecision(
            decision=decision,
            risk_level=risk_level,
            risk_score=risk_score,
            action_details=details,
            policy_version=self.policy_version,
            requires_review=requires_review,
            defense_only=True,  # Hard constraint â€” never changes
        )

    def get_review_queue_filter(self) -> list[str]:
        """Return risk levels that require manual review."""
        return [
            level for level, (_, requires_review, _) in self._decision_matrix.items()
            if requires_review
        ]


# Module-level singleton
_policy_instance: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get or create the singleton PolicyEngine instance."""
    global _policy_instance
    if _policy_instance is None:
        _policy_instance = PolicyEngine()
    return _policy_instance

