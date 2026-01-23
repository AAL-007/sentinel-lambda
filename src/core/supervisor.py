"""
SENTINEL-Λ Core Safety Supervisor
Production-grade implementation with enterprise features
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any, Union
import re
import json
from pathlib import Path
import hashlib
from collections import defaultdict
from contextlib import asynccontextmanager

import pandas as pd
from pydantic import BaseModel, Field, validator
import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Decision(str, Enum):
    """Safety decision types"""
    APPROVE = "APPROVE"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"  # For ambiguous cases


class RiskLevel(str, Enum):
    """Risk severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Domain(str, Enum):
    """Supported domains"""
    MEDICAL = "medical"
    FINANCIAL = "financial"
    LEGAL = "legal"
    EDUCATION = "education"
    GENERAL = "general"


@dataclass
class SafetyRule:
    """Safety rule definition"""
    id: str
    pattern: str
    description: str
    domain: Domain
    risk_level: RiskLevel
    action: Decision
    confidence_threshold: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskFactor:
    """Identified risk factor"""
    rule_id: str
    description: str
    risk_level: RiskLevel
    confidence: float
    evidence: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditTrail:
    """Complete audit trail for a decision"""
    audit_id: str
    query: str
    response: str
    domain: Domain
    decision: Decision
    risk_factors: List[RiskFactor]
    confidence_score: float
    timestamp: datetime
    processing_time_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    counterfactual: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "audit_id": self.audit_id,
            "query": self.query,
            "response": self.response,
            "domain": self.domain.value,
            "decision": self.decision.value,
            "risk_factors": [
                {
                    "rule_id": rf.rule_id,
                    "description": rf.description,
                    "risk_level": rf.risk_level.value,
                    "confidence": rf.confidence,
                    "evidence": rf.evidence
                }
                for rf in self.risk_factors
            ],
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "counterfactual": self.counterfactual,
            "metadata": self.metadata
        }


class SafetyRequest(BaseModel):
    """Safety evaluation request"""
    query: str = Field(..., min_length=1, max_length=5000)
    response: str = Field(..., min_length=1, max_length=10000)
    domain: Domain = Domain.GENERAL
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('query', 'response')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty or whitespace only')
        return v.strip()


class SafetyResponse(BaseModel):
    """Safety evaluation response"""
    decision: Decision
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_factors: List[Dict[str, Any]]
    audit_id: str
    processing_time_ms: int
    timestamp: datetime
    counterfactual: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)


class SafetySupervisor:
    """
    Production-grade AI Safety Supervisor
    Thread-safe, async-ready, with caching and monitoring
    """

    def __init__(
        self,
        domain: Domain = Domain.GENERAL,
        redis_url: Optional[str] = None,
        rules_path: Optional[Path] = None
    ):
        self.domain = domain
        self.rules: List[SafetyRule] = []
        self.redis_client = None
        self._initialized = False
        
        # Initialize components
        self._load_rules(rules_path)
        self._init_pattern_matchers()
        
        # Setup Redis if URL provided
        if redis_url:
            asyncio.create_task(self._init_redis(redis_url))
    
    async def _init_redis(self, redis_url: str):
        """Initialize Redis client for caching"""
        try:
            self.redis_client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
            self.redis_client = None
    
    def _load_rules(self, rules_path: Optional[Path] = None):
        """Load safety rules from file or default"""
        if rules_path and rules_path.exists():
            with open(rules_path, 'r') as f:
                rules_data = json.load(f)
                self.rules = [
                    SafetyRule(**rule) for rule in rules_data.get('rules', [])
                ]
        else:
            # Load default rules
            self._load_default_rules()
        
        logger.info(f"Loaded {len(self.rules)} safety rules for domain: {self.domain}")
    
    def _load_default_rules(self):
        """Load domain-specific default rules"""
        base_rules = [
            # Emergency detection
            SafetyRule(
                id="EMERGENCY_001",
                pattern=r"(chest pain|heart attack|stroke|seizure|unconscious)",
                description="Medical emergency detection",
                domain=Domain.MEDICAL,
                risk_level=RiskLevel.CRITICAL,
                action=Decision.BLOCK,
                metadata={"requires_immediate_action": True}
            ),
            # Suicide/self-harm
            SafetyRule(
                id="HARM_001",
                pattern=r"(suicide|kill myself|end my life|self-harm)",
                description="Self-harm risk detection",
                domain=Domain.GENERAL,
                risk_level=RiskLevel.CRITICAL,
                action=Decision.ESCALATE,
                metadata={"escalation_priority": "HIGH"}
            ),
            # Financial scams
            SafetyRule(
                id="FINANCIAL_001",
                pattern=r"(guaranteed returns|risk-free|get rich quick|insider information)",
                description="Financial scam detection",
                domain=Domain.FINANCIAL,
                risk_level=RiskLevel.HIGH,
                action=Decision.BLOCK,
                metadata={"requires_disclaimer": True}
            ),
            # Illegal activities
            SafetyRule(
                id="LEGAL_001",
                pattern=r"(how to (make|build) (bomb|explosive|weapon)|illegal drugs)",
                description="Illegal activity detection",
                domain=Domain.LEGAL,
                risk_level=RiskLevel.CRITICAL,
                action=Decision.BLOCK
            ),
            # Privacy violations
            SafetyRule(
                id="PRIVACY_001",
                pattern=r"(social security|credit card|password|secret key)",
                description="Privacy violation detection",
                domain=Domain.GENERAL,
                risk_level=RiskLevel.HIGH,
                action=Decision.ESCALATE
            ),
        ]
        
        # Filter rules by domain if not GENERAL
        if self.domain != Domain.GENERAL:
            self.rules = [r for r in base_rules if r.domain in [self.domain, Domain.GENERAL]]
        else:
            self.rules = base_rules
    
    def _init_pattern_matchers(self):
        """Initialize compiled regex patterns for performance"""
        self.compiled_patterns = {}
        for rule in self.rules:
            try:
                self.compiled_patterns[rule.id] = re.compile(
                    rule.pattern, re.IGNORECASE | re.MULTILINE
                )
            except re.error as e:
                logger.error(f"Invalid regex pattern for rule {rule.id}: {e}")
    
    def _generate_audit_id(self, query: str, response: str) -> str:
        """Generate unique audit ID"""
        content = f"{query}:{response}:{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def evaluate(
        self,
        request: SafetyRequest
    ) -> Tuple[Decision, AuditTrail]:
        """
        Main safety evaluation pipeline
        Returns decision and complete audit trail
        """
        start_time = datetime.now()
        
        # Generate audit ID
        audit_id = self._generate_audit_id(request.query, request.response)
        
        # Check cache first (if Redis is available)
        cached_result = await self._check_cache(audit_id)
        if cached_result:
            return cached_result
        
        # Execute safety checks
        risk_factors = await self._check_all_rules(request)
        
        # Calculate overall confidence
        confidence_score = self._calculate_confidence(risk_factors)
        
        # Make decision
        decision = self._make_decision(risk_factors, confidence_score)
        
        # Generate counterfactual if needed
        counterfactual = None
        if decision in [Decision.BLOCK, Decision.ESCALATE]:
            counterfactual = self._generate_counterfactual(request, risk_factors)
        
        # Calculate processing time
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Create audit trail
        audit_trail = AuditTrail(
            audit_id=audit_id,
            query=request.query,
            response=request.response,
            domain=request.domain,
            decision=decision,
            risk_factors=risk_factors,
            confidence_score=confidence_score,
            timestamp=datetime.now(),
            processing_time_ms=processing_time_ms,
            metadata=request.metadata,
            counterfactual=counterfactual,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        # Cache result
        await self._cache_result(audit_id, (decision, audit_trail))
        
        # Log for monitoring
        self._log_decision(audit_trail)
        
        return decision, audit_trail
    
    async def _check_cache(self, audit_id: str) -> Optional[Tuple[Decision, AuditTrail]]:
        """Check Redis cache for existing evaluation"""
        if not self.redis_client:
            return None
        
        try:
            cached = await self.redis_client.get(f"sentinel:audit:{audit_id}")
            if cached:
                data = json.loads(cached)
                # Reconstruct objects from cached data
                decision = Decision(data['decision'])
                audit_trail = AuditTrail(**data['audit_trail'])
                logger.info(f"Cache hit for audit: {audit_id}")
                return decision, audit_trail
        except Exception as e:
            logger.error(f"Cache check failed: {e}")
        
        return None
    
    async def _cache_result(self, audit_id: str, result: Tuple[Decision, AuditTrail]):
        """Cache evaluation result in Redis"""
        if not self.redis_client:
            return
        
        try:
            decision, audit_trail = result
            cache_data = {
                'decision': decision.value,
                'audit_trail': audit_trail.to_dict()
            }
            await self.redis_client.setex(
                f"sentinel:audit:{audit_id}",
                3600,  # 1 hour TTL
                json.dumps(cache_data)
            )
        except Exception as e:
            logger.error(f"Cache write failed: {e}")
    
    async def _check_all_rules(self, request: SafetyRequest) -> List[RiskFactor]:
        """Apply all safety rules to the request"""
        risk_factors = []
        
        # Check each rule asynchronously
        tasks = []
        for rule in self.rules:
            if rule.domain in [request.domain, Domain.GENERAL]:
                tasks.append(self._check_rule(rule, request))
        
        # Execute checks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect valid results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Rule check failed: {result}")
            elif result:
                risk_factors.append(result)
        
        return risk_factors
    
    async def _check_rule(
        self,
        rule: SafetyRule,
        request: SafetyRequest
    ) -> Optional[RiskFactor]:
        """Check a single safety rule"""
        try:
            pattern = self.compiled_patterns.get(rule.id)
            if not pattern:
                return None
            
            # Check both query and response
            text_to_check = f"{request.query}\n{request.response}"
            matches = list(pattern.finditer(text_to_check))
            
            if matches:
                evidence = matches[0].group(0)
                confidence = self._calculate_rule_confidence(rule, matches, request)
                
                return RiskFactor(
                    rule_id=rule.id,
                    description=rule.description,
                    risk_level=rule.risk_level,
                    confidence=confidence,
                    evidence=evidence,
                    context={
                        "match_count": len(matches),
                        "pattern": rule.pattern,
                        "domain": rule.domain.value
                    }
                )
        except Exception as e:
            logger.error(f"Error checking rule {rule.id}: {e}")
        
        return None
    
    def _calculate_rule_confidence(
        self,
        rule: SafetyRule,
        matches: List[re.Match],
        request: SafetyRequest
    ) -> float:
        """Calculate confidence for a rule match"""
        base_confidence = 0.8  # Base confidence for any match
        
        # Adjust based on match count
        if len(matches) > 1:
            base_confidence = min(0.95, base_confidence + (len(matches) * 0.05))
        
        # Adjust based on risk level
        risk_multipliers = {
            RiskLevel.LOW: 0.7,
            RiskLevel.MEDIUM: 0.8,
            RiskLevel.HIGH: 0.9,
            RiskLevel.CRITICAL: 1.0
        }
        base_confidence *= risk_multipliers.get(rule.risk_level, 0.8)
        
        # Adjust based on domain match
        if rule.domain == request.domain:
            base_confidence = min(1.0, base_confidence + 0.1)
        
        return round(base_confidence, 2)
    
    def _calculate_confidence(self, risk_factors: List[RiskFactor]) -> float:
        """Calculate overall confidence score"""
        if not risk_factors:
            return 1.0  # No risks = high confidence in safety
        
        # Weight by risk level
        weights = {
            RiskLevel.CRITICAL: 1.0,
            RiskLevel.HIGH: 0.8,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.LOW: 0.2
        }
        
        total_weight = 0
        weighted_sum = 0
        
        for risk in risk_factors:
            weight = weights.get(risk.risk_level, 0.5)
            total_weight += weight
            weighted_sum += risk.confidence * weight
        
        if total_weight == 0:
            return 1.0
        
        overall_confidence = weighted_sum / total_weight
        return round(overall_confidence, 2)
    
    def _make_decision(
        self,
        risk_factors: List[RiskFactor],
        confidence: float
    ) -> Decision:
        """Make final safety decision"""
        if not risk_factors:
            return Decision.APPROVE
        
        # Count risks by level
        risk_counts = defaultdict(int)
        for risk in risk_factors:
            risk_counts[risk.risk_level] += 1
        
        # Decision logic
        if risk_counts.get(RiskLevel.CRITICAL, 0) > 0:
            return Decision.BLOCK
        
        if risk_counts.get(RiskLevel.HIGH, 0) > 1:
            return Decision.BLOCK
        
        if risk_counts.get(RiskLevel.HIGH, 0) > 0 and confidence < 0.5:
            return Decision.ESCALATE
        
        if risk_counts.get(RiskLevel.MEDIUM, 0) > 2:
            return Decision.ESCALATE
        
        if confidence < 0.3:
            return Decision.REVIEW
        
        return Decision.APPROVE
    
    def _generate_counterfactual(
        self,
        request: SafetyRequest,
        risk_factors: List[RiskFactor]
    ) -> str:
        """Generate safer alternative response"""
        highest_risk = max(
            risk_factors,
            key=lambda x: list(RiskLevel).index(x.risk_level)
        ) if risk_factors else None
        
        templates = {
            Domain.MEDICAL: {
                RiskLevel.CRITICAL: (
                    "I detect discussion of a potential medical emergency. "
                    "Please call emergency services immediately or go to the nearest emergency room. "
                    "This requires urgent professional medical attention."
                ),
                RiskLevel.HIGH: (
                    "For safety reasons, I cannot provide specific medical advice. "
                    "Please consult with a licensed healthcare professional who can assess your situation."
                )
            },
            Domain.FINANCIAL: {
                RiskLevel.CRITICAL: (
                    "I cannot provide advice on potentially risky financial activities. "
                    "Please consult with a certified financial advisor or regulatory authority."
                ),
                RiskLevel.HIGH: (
                    "Investment decisions should be made with professional guidance. "
                    "Past performance does not guarantee future results. "
                    "All investments carry risk of loss."
                )
            },
            Domain.GENERAL: {
                RiskLevel.CRITICAL: (
                    "For safety reasons, I cannot provide the requested information. "
                    "If you're experiencing distress, please contact a crisis helpline or professional support."
                ),
                RiskLevel.HIGH: (
                    "I cannot assist with this request due to safety concerns. "
                    "Please consult appropriate professional resources for guidance."
                )
            }
        }
        
        domain_template = templates.get(request.domain, templates[Domain.GENERAL])
        risk_template = domain_template.get(
            highest_risk.risk_level if highest_risk else RiskLevel.HIGH,
            domain_template[RiskLevel.HIGH]
        )
        
        return risk_template
    
    def _log_decision(self, audit_trail: AuditTrail):
        """Log decision for monitoring and analytics"""
        log_entry = {
            "audit_id": audit_trail.audit_id,
            "decision": audit_trail.decision.value,
            "domain": audit_trail.domain.value,
            "confidence": audit_trail.confidence_score,
            "risk_count": len(audit_trail.risk_factors),
            "processing_time_ms": audit_trail.processing_time_ms,
            "timestamp": audit_trail.timestamp.isoformat()
        }
        
        logger.info(f"Safety decision: {json.dumps(log_entry)}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get supervisor statistics"""
        return {
            "domain": self.domain.value,
            "rule_count": len(self.rules),
            "initialized": self._initialized,
            "redis_available": self.redis_client is not None,
            "compiled_patterns": len(self.compiled_patterns)
        }
    
    async def close(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()


# Factory function for easy creation
async def create_supervisor(
    domain: Domain = Domain.GENERAL,
    redis_url: Optional[str] = None
) -> SafetySupervisor:
    """
    Factory function to create and initialize a supervisor
    """
    supervisor = SafetySupervisor(domain, redis_url)
    # Wait a moment for Redis initialization
    await asyncio.sleep(0.1)
    return supervisor