# RazorGuard Model Card

## Model Details
- **Architecture**: `HistGradientBoostingClassifier`
- **Framework**: `scikit-learn 1.5.2`
- **Training Date**: 2024-08-23
- **Version**: v1.0.0
- **Use Case**: Detection of fraudulent payment transactions.

## Intended Use
- **Primary Use**: Generating risk scores (0.0 to 1.0) for payment transactions to inform deterministic policy routing.
- **Out-of-Scope**: Not intended to directly decline transactions without human review or policy oversight. Not intended for use outside of the payment fraud domain.

## Factors
- **Demographics**: Demographic data (race, gender, age, income) are **NOT** used in this model to prevent bias.
- **Features**: 25 features are derived primarily from transaction metadata (amount, currency, merchant) and contextual behavioral data (velocity, device history, location distance).

## Metrics
Evaluated on a strictly held-out test set of 1,500 transactions.
- **Precision**: 0.8625
- **Recall**: 0.8415
- **F1 Score**: 0.8519
- **PR-AUC**: 0.9212 (Primary optimization metric due to class imbalance)
- **ROC-AUC**: 0.9837

## Business Economics Analysis
*Illustrative merchant cost assumptions:*
- Cost to review a legitimate transaction (False Positive): ₹1,650
- Cost of missing a fraudulent transaction (False Negative): ₹65,000

*Cost Evaluation (at optimal threshold 0.230):*
- FP count: 11
- FN count: 13
- Total Expected Risk Cost per 1,000 transactions: ₹44,433.33

## Training Data
Synthetic dataset generated deterministically (`seed=42`). 10,000 transactions across 200 user profiles and 50 merchants. Time-aware split:
- **Train**: 7,000 (70%)
- **Validation**: 1,500 (15%)
- **Test**: 1,500 (15%) - *Never seen during training or threshold tuning.*

## Ethical Considerations
To ensure fair and transparent operations, RazorGuard incorporates a **Bounded Evidence Agent**. Decisions are never a "black box." The ML score is paired with deterministic risk signals, and an LLM is used strictly to translate those signals into a human-readable explanation for the reviewer.
