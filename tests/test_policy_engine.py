import pytest
from app.services.policy_engine import PolicyEngine

def test_policy_engine_strictness():
    engine = PolicyEngine()
    
    # 1. Critical risk should always HOLD
    result = engine.evaluate({"risk_level": "CRITICAL", "risk_score": 0.95})
    assert result.decision == "HOLD"
    
    # 2. High risk should REVIEW
    result = engine.evaluate({"risk_level": "HIGH", "risk_score": 0.70})
    assert result.decision == "REVIEW"
    assert result.requires_review is True
    
    # 3. Medium risk with high amount should ALLOW_MONITOR (not review)
    result = engine.evaluate({
        "risk_level": "MEDIUM", 
        "risk_score": 0.40, 
        "amount": 25000, 
        "signals": []
    })
    assert result.decision == "ALLOW_MONITOR"
    
    # 4. Low risk should ALLOW
    result = engine.evaluate({"risk_level": "LOW", "risk_score": 0.10})
    assert result.decision == "ALLOW"
