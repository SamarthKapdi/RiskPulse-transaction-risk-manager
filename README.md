# RazorGuard

## AI Transaction Risk Manager

Track 02 — Razorpay AI Buildathon 2026

**"Detect risk. Explain it. Defend deterministically. Audit everything."**

---

### Problem
Merchants lose money through fraudulent and suspicious transactions, but they cannot manually inspect every transaction. Simple blocklists are brittle, and black-box ML models reject legitimate customers without explanation, creating a terrible customer experience.

### Solution
**RazorGuard** combines ML risk scoring, AI-generated evidence, deterministic policy enforcement, and persistent audit trails into a single, cohesive risk management engine.

### Why it is different
- **The ML model detects risk**: It scores transactions based on historical patterns and velocity.
- **The AI explains risk**: A bounded LLM Evidence Agent reads the signals and explains *why* the transaction was flagged in human-readable terms.
- **The policy engine controls action**: **The LLM does not control financial decisions.** A deterministic, hardcoded policy maps risk to defensive actions (ALLOW, MONITOR, REVIEW, HOLD).
- **The audit trail records everything**: Every single decision, risk score, and piece of evidence is persisted to a PostgreSQL database for compliance.

### Architecture
See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the detailed pipeline diagram.

### Key Features
* ML fraud/risk detection (HistGradientBoosting)
* Held-out evaluation metrics
* Explainable evidence via Gemini AI
* Deterministic policy engine
* False-positive economics modeling
* Persistent PostgreSQL audit trail (SQLAlchemy/Alembic)
* Real-time interactive dashboard
* Graceful AI fallback (system operates even if Gemini is down)
* Strict defense-only architecture

### Evaluation
The model was evaluated on a strictly held-out synthetic test set of 1,500 transactions.
- **PR-AUC**: 0.9699
- **ROC-AUC**: 0.9972
- **Precision**: 97.4%
- **Recall**: 90.2%

*(See [MODEL_CARD.md](docs/MODEL_CARD.md) for detailed metrics and false-positive economics)*

### Demo (Live Execution)
To start the live dashboard and backend:
```bash
docker compose build --no-cache
docker compose up -d
```
Then navigate to `http://localhost:8000/dashboard/index.html` (if hosting dashboard statically) or use the API directly.

### Docker Setup
The environment is fully Dockerized for reproducibility, running the FastAPI app, Celery worker, Redis, and PostgreSQL.
```bash
# Clean start
docker compose down -v
docker compose build
docker compose up -d
```

### Environment Variables
Copy `.env.example` to `.env`:
```env
# Example configuration
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/pipeline_db
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your_gemini_key_here
```

### API
- `POST /risk/analyze`: Submit a transaction for full risk assessment and policy action.
- `GET /risk/{transaction_id}/explanation`: Retrieve the AI-generated evidence.
- `GET /risk/evaluation/metrics`: Fetch the latest held-out model metrics and business economics.
- `GET /risk/audit/{transaction_id}`: Fetch the persistent audit record.

### Testing
RazorGuard includes a comprehensive test suite (29 tests) verifying everything from anomaly detection algorithms to the deterministic policy engine.
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pytest tests/ -v
```
*(All 29 tests pass successfully)*

### Limitations
- The provided dataset is highly synthetic and designed to prove the architecture. Synthetic benchmark performance (PR-AUC 0.9699) is **not** equivalent to production fraud performance in the real world.
- The business economics (False Positive costs) use illustrative merchant assumptions.
