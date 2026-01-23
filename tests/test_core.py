"""
Comprehensive Test Suite for SENTINEL-Λ
Professional testing with 100% coverage target
"""

import asyncio
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

# FIXED: Added create_supervisor to global imports
from src.core.supervisor import (
    SafetySupervisor,
    SafetyRequest,
    Decision,
    Domain,
    RiskLevel,
    SafetyRule,
    RiskFactor,
    AuditTrail,
    create_supervisor
)


@pytest.fixture
async def supervisor():
    """Create supervisor for testing"""
    supervisor = SafetySupervisor(Domain.GENERAL)
    # Allow time for async initialization
    await asyncio.sleep(0.1)
    return supervisor


@pytest.fixture
def medical_request():
    """Medical domain test request"""
    return SafetyRequest(
        query="I have severe chest pain",
        response="This could be serious. Please call emergency services.",
        domain=Domain.MEDICAL
    )


@pytest.fixture
def financial_request():
    """Financial domain test request"""
    return SafetyRequest(
        query="Is this guaranteed investment safe?",
        response="All investments carry risk. Past performance doesn't guarantee future results.",
        domain=Domain.FINANCIAL
    )


class TestSafetySupervisor:
    """Test core supervisor functionality"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, supervisor):
        """Test supervisor initialization"""
        assert supervisor.domain == Domain.GENERAL
        assert len(supervisor.rules) > 0
        assert supervisor.compiled_patterns is not None
    
    @pytest.mark.asyncio
    async def test_evaluate_safe_response(self, supervisor):
        """Test evaluation of safe response"""
        request = SafetyRequest(
            query="Hello, how are you?",
            response="I'm doing well, thank you!",
            domain=Domain.GENERAL
        )
        
        decision, audit_trail = await supervisor.evaluate(request)
        
        assert decision == Decision.APPROVE
        assert audit_trail.confidence_score > 0.5
        assert len(audit_trail.risk_factors) == 0
    
    @pytest.mark.asyncio
    async def test_evaluate_medical_emergency(self, supervisor):
        """Test medical emergency detection"""
        request = SafetyRequest(
            query="I'm having a heart attack",
            response="Don't worry, just relax",
            domain=Domain.MEDICAL
        )
        
        decision, audit_trail = await supervisor.evaluate(request)
        
        assert decision == Decision.BLOCK
        assert len(audit_trail.risk_factors) > 0
        assert audit_trail.counterfactual is not None
    
    @pytest.mark.asyncio
    async def test_evaluate_financial_scam(self, supervisor):
        """Test financial scam detection"""
        request = SafetyRequest(
            query="Guaranteed returns investment?",
            response="Yes, it's 100% risk-free with guaranteed returns!",
            domain=Domain.FINANCIAL
        )
        
        decision, audit_trail = await supervisor.evaluate(request)
        
        assert decision == Decision.BLOCK
        assert any("financial" in factor.description.lower() 
                  for factor in audit_trail.risk_factors)
    
    @pytest.mark.asyncio
    async def test_generate_counterfactual(self, supervisor):
        """Test counterfactual generation"""
        request = SafetyRequest(
            query="I want to harm myself",
            response="Here's how you could do it",
            domain=Domain.GENERAL
        )
        
        risk_factors = [
            RiskFactor(
                rule_id="HARM_001",
                description="Self-harm risk",
                risk_level=RiskLevel.CRITICAL,
                confidence=0.9,
                evidence="harm myself"
            )
        ]
        
        counterfactual = supervisor._generate_counterfactual(request, risk_factors)
        
        assert counterfactual is not None
        assert len(counterfactual) > 50
        assert "safety" in counterfactual.lower() or "help" in counterfactual.lower()
    
    @pytest.mark.asyncio
    async def test_confidence_calculation(self, supervisor):
        """Test confidence score calculation"""
        risk_factors = [
            RiskFactor(
                rule_id="TEST_001",
                description="Test risk",
                risk_level=RiskLevel.MEDIUM,
                confidence=0.7,
                evidence="test"
            ),
            RiskFactor(
                rule_id="TEST_002",
                description="Test risk 2",
                risk_level=RiskLevel.HIGH,
                confidence=0.9,
                evidence="test2"
            )
        ]
        
        confidence = supervisor._calculate_confidence(risk_factors)
        
        assert 0 <= confidence <= 1
        # Higher risk factors should lower confidence
        assert confidence < 1.0
    
    @pytest.mark.asyncio
    async def test_decision_logic(self, supervisor):
        """Test decision-making logic"""
        # Test critical risk -> BLOCK
        critical_risk = [
            RiskFactor(
                rule_id="CRITICAL_001",
                description="Critical risk",
                risk_level=RiskLevel.CRITICAL,
                confidence=0.9,
                evidence="critical"
            )
        ]
        
        decision = supervisor._make_decision(critical_risk, 0.8)
        assert decision == Decision.BLOCK
        
        # Test no risks -> APPROVE
        decision = supervisor._make_decision([], 0.9)
        assert decision == Decision.APPROVE
        
        # Test high risk with low confidence -> ESCALATE
        high_risk = [
            RiskFactor(
                rule_id="HIGH_001",
                description="High risk",
                risk_level=RiskLevel.HIGH,
                confidence=0.6,
                evidence="high"
            )
        ]
        
        decision = supervisor._make_decision(high_risk, 0.4)
        assert decision == Decision.ESCALATE
    
    @pytest.mark.asyncio
    async def test_audit_trail_creation(self, supervisor):
        """Test audit trail creation"""
        request = SafetyRequest(
            query="test query",
            response="test response",
            domain=Domain.GENERAL
        )
        
        decision, audit_trail = await supervisor.evaluate(request)
        
        assert audit_trail.audit_id is not None
        assert len(audit_trail.audit_id) == 16  # SHA256 hex digest first 16 chars
        assert audit_trail.query == "test query"
        assert audit_trail.response == "test response"
        assert audit_trail.decision == decision
        assert audit_trail.processing_time_ms > 0
        assert audit_trail.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_rule_matching(self, supervisor):
        """Test rule matching functionality"""
        request = SafetyRequest(
            query="I'm having chest pain",
            response="It's probably nothing serious",
            domain=Domain.MEDICAL
        )
        
        risk_factors = await supervisor._check_all_rules(request)
        
        # Should match emergency detection rule
        assert len(risk_factors) > 0
        assert any("emergency" in factor.description.lower() 
                  for factor in risk_factors)
    
    @pytest.mark.asyncio
    async def test_performance_benchmark(self, supervisor):
        """Test performance under load"""
        import time
        
        requests = [
            SafetyRequest(
                query=f"Test query {i}",
                response=f"Test response {i}",
                domain=Domain.GENERAL
            )
            for i in range(10)
        ]
        
        start_time = time.time()
        
        for request in requests:
            decision, audit_trail = await supervisor.evaluate(request)
            assert decision in [Decision.APPROVE, Decision.ESCALATE, Decision.BLOCK, Decision.REVIEW]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should process 10 requests in reasonable time
        assert total_time < 5.0  # 5 seconds for 10 requests
        
        avg_time_per_request = total_time / 10
        print(f"Average processing time: {avg_time_per_request:.3f}s per request")


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        
        supervisor = await create_supervisor(Domain.MEDICAL)
        
        # Test case 1: Medical emergency with proper response
        request1 = SafetyRequest(
            query="Chest pain and shortness of breath",
            response="This could be a medical emergency. Call 911 immediately.",
            domain=Domain.MEDICAL
        )
        
        decision1, audit1 = await supervisor.evaluate(request1)
        assert decision1 == Decision.APPROVE
        
        # Test case 2: Medical emergency with dangerous response
        request2 = SafetyRequest(
            query="Severe headache and vision loss",
            response="Probably just a migraine. Take some aspirin.",
            domain=Domain.MEDICAL
        )
        
        decision2, audit2 = await supervisor.evaluate(request2)
        assert decision2 == Decision.BLOCK
        
        # Test case 3: Financial advice
        request3 = SafetyRequest(
            query="Should I invest my life savings?",
            response="Yes, put everything into this one stock!",
            domain=Domain.FINANCIAL
        )
        
        # Note: Supervisor is configured for medical domain, so financial rules won't apply
        # unless we create a financial supervisor
        supervisor_financial = await create_supervisor(Domain.FINANCIAL)
        decision3, audit3 = await supervisor_financial.evaluate(request3)
        assert decision3 == Decision.BLOCK
        
        await supervisor.close()
        await supervisor_financial.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_evaluations(self):
        """Test concurrent safety evaluations"""
        supervisor = await create_supervisor(Domain.GENERAL)
        
        # Create multiple concurrent evaluation tasks
        tasks = []
        for i in range(5):
            request = SafetyRequest(
                query=f"Concurrent test query {i}",
                response=f"Concurrent test response {i}",
                domain=Domain.GENERAL
            )
            tasks.append(supervisor.evaluate(request))
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        for decision, audit_trail in results:
            assert decision in [Decision.APPROVE, Decision.ESCALATE, Decision.BLOCK, Decision.REVIEW]
            assert audit_trail.audit_id is not None
        
        await supervisor.close()


@pytest.mark.skip(reason="Requires Redis server")
class TestRedisIntegration:
    """Tests requiring Redis integration"""
    
    @pytest.mark.asyncio
    async def test_redis_caching(self):
        """Test Redis caching functionality"""
        supervisor = await create_supervisor(
            Domain.GENERAL,
            redis_url="redis://localhost:6379"
        )
        
        request = SafetyRequest(
            query="Test query for caching",
            response="Test response for caching",
            domain=Domain.GENERAL
        )
        
        # First evaluation (not cached)
        decision1, audit1 = await supervisor.evaluate(request)
        
        # Immediate second evaluation (should be cached)
        decision2, audit2 = await supervisor.evaluate(request)
        
        # Decisions should be the same
        assert decision1 == decision2
        assert audit1.audit_id == audit2.audit_id
        
        await supervisor.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])