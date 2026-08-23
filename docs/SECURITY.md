# Security & Defense-Only Architecture

RazorGuard is designed to comply strictly with the "Defense-Only" requirement of the Razorpay AI Buildathon 2026.

## 1. Deterministic Policy Enforcement
The `PolicyEngine` (`app/services/policy_engine.py`) is the ultimate arbiter of all risk decisions. 
- It maps the output of the ML model directly into one of four actions: `ALLOW`, `ALLOW_MONITOR`, `REVIEW`, or `HOLD`.
- The LLM **cannot** override or influence these decisions.

## 2. Bounded LLM Agent
The Gemini 1.5 model is used exclusively as an "Evidence & Explanation Agent" (`app/services/evidence_agent.py`).
- **Input:** It only receives structured risk signals (e.g., "Velocity anomaly detected: 10 txns in 1 hour") and the final deterministic decision.
- **Output:** It is strictly prompted to output a human-readable explanation and an evidence summary. 
- **Validation:** If the LLM produces malformed output or attempts to hallucinate actions outside its bounds, the system gracefully degrades to a deterministic string-template fallback, ensuring zero downtime and zero offensive capability.

## 3. Safe Fallbacks
If the `GEMINI_API_KEY` is missing or the external API is down, the system does not fail open or fail closed; it falls back to a deterministic explanation generation system.

## 5. Auditability
Every risk decision is persistently logged to the `risk_audit_trail` PostgreSQL table using SQLAlchemy and Alembic. This includes the transaction ID, timestamp, risk score, exact risk level, policy action, and the model version used to make the decision.

## 6. Secrets Management
All sensitive configurations (like the `GEMINI_API_KEY` and `DATABASE_URL`) are loaded exclusively from environment variables or a `.env` file (which is ignored in git). The `.env.example` file contains only placeholders. No secrets are ever committed to the repository.

## 7. API Validation & Database Security
The FastAPI application strictly types and validates all incoming requests using Pydantic models. Database queries are parameterized by SQLAlchemy, completely eliminating SQL injection vectors. No stack traces or sensitive internals are exposed in HTTP response payloads.
