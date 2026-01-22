from enum import Enum

class Decision(str, Enum):
    """Explicit system states - structural enforcement"""
    APPROVE = "APPROVE"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"
    
class DecisionReason(str, Enum):

    """Transparent reasons for decisions"""
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    HIGH_RISK_NO_ESCALATION = "HIGH_RISK_NO_ESCALATION"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    PASSED_ALL_CHECKS = "PASSED_ALL_CHECKS"
    