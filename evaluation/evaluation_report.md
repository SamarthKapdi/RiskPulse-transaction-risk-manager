# RazorGuard — Evaluation Report

> Generated: 2026-08-23T12:46:13.062609
> Model: hist_gradient_boosting
> Threshold: 0.23000000000000004

## Dataset

| Set | Samples | Fraud Rate |
|-----|---------|------------|
| Train | 7000 | 5.16% |
| Test (held-out) | 1500 | 5.47% |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Precision | 0.8625 |
| Recall | 0.8415 |
| F1 Score | 0.8519 |
| PR-AUC | 0.9212 |
| ROC-AUC | 0.9837 |
| False Positive Rate | 0.0078 |
| False Negative Rate | 0.1585 |

## Confusion Matrix

| | Predicted Legit | Predicted Fraud |
|---|---|---|
| **Actual Legit** | 1407 | 11 |
| **Actual Fraud** | 13 | 69 |

## Cost Analysis

> ⚠️ Illustrative merchant cost assumptions

| Metric | Value |
|--------|-------|
| Review cost per legit flagged | ₹150.0 |
| Cost per missed fraud | ₹5000.0 |
| Total FP cost | ₹1,650.00 |
| Total FN cost | ₹65,000.00 |
| **Total expected cost** | **₹66,650.00** |
| Cost per 1,000 transactions | ₹44,433.33 |

## Threshold / Cost Analysis

| Threshold | Precision | Recall | F1 | FP | FN | Total Cost (₹) |
|-----------|-----------|--------|-----|-----|-----|-----------------|
| 0.10 | 0.8452 | 0.8659 | 0.8554 | 13 | 11 | 56,950.00 |
| 0.20 | 0.8642 | 0.8537 | 0.8589 | 11 | 12 | 61,650.00 |
| 0.30 | 0.8701 | 0.8171 | 0.8428 | 10 | 15 | 76,500.00 |
| 0.40 | 0.8904 | 0.7927 | 0.8387 | 8 | 17 | 86,200.00 |
| 0.50 | 0.9275 | 0.7805 | 0.8477 | 5 | 18 | 90,750.00 |
| 0.60 | 0.9403 | 0.7683 | 0.8456 | 4 | 19 | 95,600.00 |
| 0.70 | 0.9844 | 0.7683 | 0.8630 | 1 | 19 | 95,150.00 |
| 0.80 | 0.9844 | 0.7683 | 0.8630 | 1 | 19 | 95,150.00 |
| 0.90 | 0.9841 | 0.7561 | 0.8552 | 1 | 20 | 100,150.00 |

## Risk Level Analysis

| Level | Count | Actual Fraud | Predicted Fraud | Precision |
|-------|-------|-------------|-----------------|-----------|
| LOW | 1423 | 15 | 3 | 0.6667 |
| MEDIUM | 10 | 4 | 10 | 0.4000 |
| HIGH | 4 | 1 | 4 | 0.2500 |
| CRITICAL | 63 | 62 | 63 | 0.9841 |

---

*All metrics from actual model execution on held-out test data.*
*No metrics have been fabricated.*