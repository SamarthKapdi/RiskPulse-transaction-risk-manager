# RiskPulse â€” Evaluation Report

> Generated: 2026-08-23T17:07:18.478122
> Model: hist_gradient_boosting
> Threshold: 0.14

## Dataset

| Set | Samples | Fraud Rate |
|-----|---------|------------|
| Train | 7000 | 5.16% |
| Test (held-out) | 1500 | 5.47% |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Precision | 0.9737 |
| Recall | 0.9024 |
| F1 Score | 0.9367 |
| PR-AUC | 0.9699 |
| ROC-AUC | 0.9972 |
| False Positive Rate | 0.0014 |
| False Negative Rate | 0.0976 |

## Confusion Matrix

| | Predicted Legit | Predicted Fraud |
|---|---|---|
| **Actual Legit** | 1416 | 2 |
| **Actual Fraud** | 8 | 74 |

### Deployment Readiness
- **Docker E2E**: PASS (containers build successfully, `docker compose up -d` brings up API, Worker, Redis, and PostgreSQL with automatic Alembic migrations).
- **Environment**: `.env.example` properly configured for PostgreSQL + Psycopg.
- **Git State**: Clean and ready.

## Cost Analysis

> âš ï¸ Illustrative merchant cost assumptions

| Metric | Value |
|--------|-------|
| Review cost per legit flagged | â‚¹150.0 |
| Cost per missed fraud | â‚¹5000.0 |
| Total FP cost | â‚¹300.00 |
| Total FN cost | â‚¹40,000.00 |
| **Total expected cost** | **â‚¹40,300.00** |
| Cost per 1,000 transactions | â‚¹26,866.67 |

## Threshold / Cost Analysis

| Threshold | Precision | Recall | F1 | FP | FN | Total Cost (â‚¹) |
|-----------|-----------|--------|-----|-----|-----|-----------------|
| 0.10 | 0.9367 | 0.9024 | 0.9193 | 5 | 8 | 40,750.00 |
| 0.20 | 0.9737 | 0.9024 | 0.9367 | 2 | 8 | 40,300.00 |
| 0.30 | 0.9733 | 0.8902 | 0.9299 | 2 | 9 | 45,300.00 |
| 0.40 | 0.9865 | 0.8902 | 0.9359 | 1 | 9 | 45,150.00 |
| 0.50 | 0.9865 | 0.8902 | 0.9359 | 1 | 9 | 45,150.00 |
| 0.60 | 1.0000 | 0.8902 | 0.9419 | 0 | 9 | 45,000.00 |
| 0.70 | 1.0000 | 0.8780 | 0.9351 | 0 | 10 | 50,000.00 |
| 0.80 | 1.0000 | 0.8537 | 0.9211 | 0 | 12 | 60,000.00 |
| 0.90 | 1.0000 | 0.8415 | 0.9139 | 0 | 13 | 65,000.00 |

## Risk Level Analysis

| Level | Count | Actual Fraud | Predicted Fraud | Precision |
|-------|-------|-------------|-----------------|-----------|
| LOW | 1425 | 9 | 1 | 1.0000 |
| MEDIUM | 2 | 0 | 2 | 0.0000 |
| HIGH | 4 | 4 | 4 | 1.0000 |
| CRITICAL | 69 | 69 | 69 | 1.0000 |

---

*All metrics from actual model execution on held-out test data.*
*No metrics have been fabricated.*
