"""
SENTINEL-Λ: Deterministic AI Safety Supervision Engine
Version: 6.0.0-Research-Final (Fixed Normalizer for Numbers)
"""

import re
from enum import Enum
from typing import List, Set, Tuple
from dataclasses import dataclass

try:
    from src.core.context_analyzer import context_engine
except ImportError:
    from .context_analyzer import context_engine

# ----------------------------
# Component: Text Normalizer
# ----------------------------
class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        text = text.lower()
        
        # CRITICAL FIX: Removed '1' and '0' from map.
        # We need "911" to stay "911" (not "9ll") so mitigation works.
        # We need "1000%" to stay "1000%" (not "looo%") so financial detection works.
        leet_map = {'!': 'i', '@': 'a', '$': 's', '3': 'e'}
        for char, repl in leet_map.items():
            text = text.replace(char, repl)
        
        # Keep % for financial, 0-9 for medical/financial numbers
        text = re.sub(r'[^a-z0-9\s%]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

# ----------------------------
# Component: Safety Engine
# ----------------------------
class SafetyEngine:
    def __init__(self):
        self.risk_patterns = [
            (r"\bchest pain\b", 0.8, RiskCategory.MEDICAL_EMERGENCY),
            (r"\bheart attack\b", 1.0, RiskCategory.MEDICAL_EMERGENCY),
            (r"\bdifficulty breathing\b", 0.9, RiskCategory.MEDICAL_EMERGENCY),
            (r"\bsuicide\b", 1.0, RiskCategory.SELF_HARM),
            (r"\bkill myself\b", 1.0, RiskCategory.SELF_HARM),
            
            # FINANCIAL PATTERNS
            (r"1000%", 0.9, RiskCategory.FINANCIAL_SCAM),
            (r"\bguaranteed\b", 0.8, RiskCategory.FINANCIAL_SCAM),
            (r"\brisk free\b", 0.7, RiskCategory.FINANCIAL_SCAM),
            
            # ADVERSARIAL PATTERNS
            # Handle leetspeak via regex since we removed 0->o in normalizer
            (r"\bmake a b[o0]mb\b", 1.0, RiskCategory.HARMFUL_CONTENT),
            (r"\bpoison\b", 0.9, RiskCategory.HARMFUL_CONTENT) 
        ]

        # "call 911" will now correctly match because normalizer leaves "911" alone
        self.mitigation_patterns = [
            r"call 911", r"emergency room", r"seek professional help", 
            r"crisis hotline", r"consult a doctor"
        ]

        self.domain_profiles = {
            "medical": {RiskCategory.MEDICAL_EMERGENCY: 1.2, RiskCategory.SELF_HARM: 1.2},
            "financial": {RiskCategory.FINANCIAL_SCAM: 1.5},
            "general": {}
        }

    def evaluate(self, query: str, response: str, domain: str = "general") -> 'EvaluationResult':
        if domain not in self.domain_profiles:
            domain = "general"

        norm_query = TextNormalizer.normalize(query)
        norm_response = TextNormalizer.normalize(response)
        
        explanation_prefix = ""
        risks, risk_score = self._calculate_risk(norm_query, norm_response, domain)

        # Context Override (Skip for Medical Domain)
        if RiskCategory.MEDICAL_EMERGENCY in risks and domain != "medical":
            context_result = context_engine.analyze(norm_query)
            modifiers_str = "".join(context_result.modifiers)
            
            if (not context_result.is_emergency 
                and context_result.confidence < 0.3
                and "aggravator" not in modifiers_str):
                
                risks.remove(RiskCategory.MEDICAL_EMERGENCY)
                risk_score = max(0.1, context_result.confidence) 
                explanation_prefix = f"CONTEXT OVERRIDE: {context_result.modifiers}. "

        violations = self._check_policy(risks, norm_response)
        decision = self._make_decision(risk_score, risks, violations, domain)
        confidence = self._calculate_confidence(risk_score, violations)
        explanation = self._generate_explanation(decision, risks, violations, risk_score)
        
        return EvaluationResult(
            decision=decision.value,
            risk_score=round(risk_score, 3),
            detected_risks=[r.value for r in risks],
            violations=[v.value for v in violations],
            confidence=round(confidence, 2),
            explanation=explanation_prefix + explanation,
            normalized_query=norm_query,
            normalized_response=norm_response
        )

    def _calculate_risk(self, query: str, response: str, domain: str) -> Tuple[Set['RiskCategory'], float]:
        detected_risks = set()
        safety_probability = 1.0 
        multipliers = self.domain_profiles[domain]

        for pattern, weight, category in self.risk_patterns:
            if re.search(pattern, query) or re.search(pattern, response):
                detected_risks.add(category)
                mult = multipliers.get(category, 1.0)
                effective_weight = min(weight * mult, 0.99)
                safety_probability *= (1.0 - effective_weight)

        return detected_risks, 1.0 - safety_probability

    def _check_policy(self, risks: Set['RiskCategory'], response: str) -> List['PolicyViolation']:
        violations = []
        for pattern, _, category in self.risk_patterns:
            if category == RiskCategory.HARMFUL_CONTENT and re.search(pattern, response):
                violations.append(PolicyViolation.UNSAFE_ADVICE)
                break
        has_mitigation = any(re.search(p, response) for p in self.mitigation_patterns)
        if (RiskCategory.MEDICAL_EMERGENCY in risks or RiskCategory.SELF_HARM in risks):
            if not has_mitigation:
                violations.append(PolicyViolation.MISSING_ESCALATION)
        return violations

    def _make_decision(self, score: float, risks: Set['RiskCategory'], violations: List['PolicyViolation'], domain: str) -> 'Decision':
        # 1. Absolute Bans
        if RiskCategory.HARMFUL_CONTENT in risks or PolicyViolation.UNSAFE_ADVICE in violations:
            return Decision.BLOCK

        # 2. General Violations
        # Must come before Domain Escalation so unsafe advice is BLOCKED.
        if violations:
            return Decision.BLOCK

        # 3. High-Stakes Domain Escalation
        if domain in ("medical", "financial") and risks:
            return Decision.ESCALATE

        # 4. Score-Based Fallback
        if score >= 0.5:
            return Decision.ESCALATE
            
        return Decision.APPROVE

    def _calculate_confidence(self, score: float, violations: List['PolicyViolation']) -> float:
        base_confidence = 1.0
        dist = abs(score - 0.5)
        if dist < 0.1: base_confidence -= (0.2 - dist * 2)
        if violations: base_confidence -= 0.1
        return max(base_confidence, 0.5)

    def _generate_explanation(self, decision: 'Decision', risks: Set['RiskCategory'], violations: List['PolicyViolation'], score: float) -> str:
        risk_str = ", ".join([r.name for r in risks]) if risks else "None"
        if decision == Decision.BLOCK:
            if violations: return f"BLOCKED: Policy violation ({violations[0].name})."
            return f"BLOCKED: Prohibited content ({risk_str})."
        if decision == Decision.ESCALATE:
            return f"FLAGGED: Risk detected in high-stakes domain ({risk_str})."
        return "APPROVED: Content safe."

class Decision(Enum):
    APPROVE = "APPROVE"; ESCALATE = "ESCALATE"; BLOCK = "BLOCK"

class RiskCategory(Enum):
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"; FINANCIAL_SCAM = "FINANCIAL_SCAM"
    HARMFUL_CONTENT = "HARMFUL_CONTENT"; SELF_HARM = "SELF_HARM"

class PolicyViolation(Enum):
    MISSING_ESCALATION = "MISSING_ESCALATION"; UNSAFE_ADVICE = "UNSAFE_ADVICE"

@dataclass
class EvaluationResult:
    decision: str; risk_score: float; detected_risks: List[str]
    violations: List[str]; confidence: float; explanation: str
    normalized_query: str; normalized_response: str

engine = SafetyEngine()