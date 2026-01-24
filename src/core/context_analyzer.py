"""
SENTINEL-Λ: Semantic Context Analyzer
Heuristic engine for resolving ambiguity in safety-critical queries.
"""

import re
from dataclasses import dataclass, field
from typing import List

@dataclass
class ContextResult:
    is_medical_context: bool = False
    is_emergency: bool = False
    confidence: float = 0.0
    modifiers: List[str] = field(default_factory=list)
    time_frame: str = "unknown"

class ContextAnalyzer:
    def __init__(self):
        # 1. Hard Negations: Absolute rule-outs
        self.hard_negations = [
            r"\bno (chest )?pain\b",
            r"\bdon'?t have\b",
            r"\bnot (experiencing|feeling)\b",
            r"\bjust curious\b",
            r"\bhypothetical\b"
        ]

        # 2. Mitigating Factors: Lower risk (Pattern, Weight)
        self.mitigators = [
            (r"\bafter (eating|food|meal|dinner)\b", 0.5),
            (r"\bafter (workout|exercise|gym)\b", 0.3),
            (r"\bmild\b", 0.2),
            (r"\bchronic\b", 0.4),
            (r"\bused to have\b", 0.8),
            (r"\blast (week|month|year)\b", 0.6)
        ]

        # 3. Aggravating Factors: Increase risk (Pattern, Weight)
        self.aggravators = [
            (r"\b(severe|crushing|stabbing|unbearable)\b", 0.5),
            (r"\bradiating\b", 0.4),
            (r"\b(jaw|arm|back) pain\b", 0.4),
            (r"\bsweating\b", 0.3),
            (r"\bcan'?t breathe\b", 0.6),
            (r"\bpassed out\b", 0.7),
            (r"\bnow\b", 0.2)
        ]
        
        # Medical Trigger Keywords for context detection
        self.med_triggers = ["pain", "chest", "heart", "breath", "doctor", "symptom"]

    def analyze(self, text: str) -> ContextResult:
        text = text.lower()
        result = ContextResult()
        
        # Step 0: Detect Medical Domain
        if any(k in text for k in self.med_triggers):
            result.is_medical_context = True

        # Step 1: Check Hard Negations
        for pattern in self.hard_negations:
            if re.search(pattern, text):
                result.is_emergency = False
                result.modifiers.append(f"negation:{pattern}")
                return result

        # Step 2: Calculate Semantic Risk Score
        risk_score = 0.0
        
        # Apply Aggravators
        for pattern, weight in self.aggravators:
            if re.search(pattern, text):
                risk_score += weight
                result.modifiers.append(f"aggravator:{pattern}")

        # Apply Mitigators
        for pattern, weight in self.mitigators:
            if re.search(pattern, text):
                risk_score -= weight
                result.modifiers.append(f"mitigator:{pattern}")
                
                if "last" in pattern or "used to" in pattern:
                    result.time_frame = "historical"

        # Step 3: Threshold Logic & Residual Confidence
        if risk_score > 0.3:
            result.is_emergency = True
            result.confidence = min(risk_score, 1.0)
        else:
            result.is_emergency = False
            # Research Win: Non-emergencies retain residual uncertainty
            result.confidence = max(0.0, risk_score + 0.1)

        return result

# Singleton
context_engine = ContextAnalyzer()