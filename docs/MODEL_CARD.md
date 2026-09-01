# RiskPulse Model Card

## Model Details
- **Architecture**: `HistGradientBoostingClassifier`
- **Framework**: `scikit-learn 1.5.2`
- **Training Date**: 2026-08-23
- **Version**: v1.0.0
- **Use Case**: Detection of fraudulent payment transactions.

## Intended Use
- **Primary Use**: Generating risk scores (0.0 to 1.0) for payment transactions to inform deterministic policy routing.
- **Out-of-Scope**: Not intended to directly decline transactions without human review or policy oversight. Not intended for use outside of the payment fraud domain.

## Factors
- **Demographics**: Demographic data (race, gender, age, income) are **NOT** used in this model to prevent bias.
- **Features**: 23 features are derived primarily from transaction metadata (amount, currency, merchant) and contextual behavioral data (velocity, device history, location distance).

## Metrics
Evaluated on a strictly held-out test set of 1,500 transactions.
- **Precision**: 0.9737
- **Recall**: 0.9024
- **F1 Score**: 0.9367
- **PR-AUC**: 0.9699 (Primary optimization metric due to class imbalance)
- **ROC-AUC**: 0.9972

## Business Economics Analysis
*Illustrative merchant cost assumptions:*
- Cost to review a legitimate transaction (False Positive): ₹150
- Cost of missing a fraudulent transaction (False Negative): ₹5000

*Cost Evaluation (at optimal threshold 0.140):*
- FP count: 2
- FN count: 8
- Total Expected Risk Cost per 1,000 transactions: ₹26,866.67

## Training Data
Synthetic dataset generated deterministically (`seed=42`). 10,000 transactions across 200 user profiles and 50 merchants. Time-aware split:
- **Train**: 7,000 (70%)
- **Validation**: 1,500 (15%)
- **Test**: 1,500 (15%) - *Never seen during training or threshold tuning.*

## Ethical Considerations
To ensure fair and transparent operations, RiskPulse incorporates a **Bounded Evidence Agent**. Decisions are never a "black box." The ML score is paired with deterministic risk signals, and an LLM is used strictly to translate those signals into a human-readable explanation for the reviewer.

## Limitations
- **This is a synthetic dataset created for buildathon evaluation and does not represent production fraud performance.** The PR-AUC of 0.9699 was measured on a held-out synthetic test set and should not be interpreted as real-world production accuracy.
- The model has not been validated against production payment data from any merchant.
- The false-positive economics use illustrative cost assumptions, not real merchant loss figures.
