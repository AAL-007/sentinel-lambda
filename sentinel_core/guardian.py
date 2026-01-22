from typing import Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

from .decision_enums import Decision, DecisionReason
from .config_loader import ConfigLoader
from .scorers.confidence import ConfidenceScorer
from .scorers.semantic import SemanticScorer

class GuardianEngine:
    """Core safety supervision engine"""
    
    def _init_(self, config_dir: str = "configs"):
        # Load deterministic configurations
        self.config_loader = ConfigLoader(config_dir)
        self.configs = self.config_loader.load_all_configs()
        
        # Initialize scorers
        thresholds = self.configs.get('thresholds', {})
        
        self.confidence_scorer = ConfidenceScorer(
            hedging_words=thresholds.get('confidence', {}).get('hedging_words', [])
        )
        
        # Simple semantic scorer with predefined safe responses
        safe_responses = [
            "Consult a healthcare professional for medical advice.",
            "If you're experiencing severe symptoms, seek immediate medical attention.",
            "This information is not a substitute for professional medical advice."
        ]
        self.semantic_scorer = SemanticScorer(safe_responses)
        
        # Get thresholds
        self.confidence_threshold = thresholds.get('confidence', {}).get('threshold', 0.7)
        self.similarity_threshold = thresholds.get('semantic', {}).get('similarity_threshold', 0.75)
        
        # Rules
        self.rules = self.configs.get('rules', {}).get('rules', [])
        self.emergency_phrases = self.configs.get('rules', {}).get('emergency_escalation_phrases', [])
        
    def _has_emergency_escalation(self, response: str) -> bool:
        """Check if response contains emergency escalation phrases"""
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in self.emergency_phrases)
    
    def _detect_high_severity(self, query: str) -> bool:
        """Check if query contains high-risk indicators"""
        query_lower = query.lower()
        indicators = self.configs.get('thresholds', {}).get('severity', {}).get('high_risk_indicators', [])
        return any(indicator in query_lower for indicator in indicators)
    
    def _check_safety_violation(self, query: str, response: str) -> Optional[Dict]:
        """Check for unsafe patterns"""
        unsafe_patterns = self.configs.get('thresholds', {}).get('safety', {}).get('unsafe_patterns', [])
        response_lower = response.lower()
        
        for pattern_info in unsafe_patterns:
            pattern = pattern_info.get('pattern', '').lower()
            context = pattern_info.get('context', '').lower()
            
            if pattern in response_lower and context in response_lower:
                return {
                    "violation": pattern_info.get('violation', 'Unsafe pattern detected'),
                    "pattern": pattern,
                    "context": context
                }
        
        return None
    
    def evaluate(self, query: str, ai_response: str) -> Dict[str, Any]:
        """Main evaluation pipeline - completely deterministic"""
        
        # 1. Calculate scores (deterministic)
        confidence_score = self.confidence_scorer.calculate(ai_response)
        semantic_score, closest_match = self.semantic_scorer.calculate(ai_response)
        
        # 2. Run safety checks
        is_high_severity = self._detect_high_severity(query)
        has_emergency_escalation = self._has_emergency_escalation(ai_response)
        safety_violation = self._check_safety_violation(query, ai_response)
        
        # 3. Apply deterministic rules
        decision = Decision.APPROVE
        reason = DecisionReason.PASSED_ALL_CHECKS
        counterfactual = None
        
        # Apply rules in order
        for rule in self.rules:
            condition_met = False
            
            if rule['name'] == "SAFETY_VIOLATION" and safety_violation:
                condition_met = True
                decision = Decision.BLOCK
                reason = DecisionReason.SAFETY_VIOLATION
                counterfactual = f"Response would be APPROVED if it did not contain unsafe pattern: {safety_violation['pattern']}"
                break
                
            elif rule['name'] == "HIGH_SEVERITY_NO_ESCALATION" and is_high_severity and not has_emergency_escalation:
                condition_met = True
                decision = Decision.BLOCK
                reason = DecisionReason.HIGH_RISK_NO_ESCALATION
                counterfactual = "Response would be APPROVED if it included emergency referral advice"
                break
                
            elif rule['name'] == "LOW_CONFIDENCE" and confidence_score < self.confidence_threshold:
                condition_met = True
                decision = Decision.ESCALATE
                reason = DecisionReason.LOW_CONFIDENCE
                counterfactual = f"Response would be APPROVED with confidence score ≥ {self.confidence_threshold} (current: {confidence_score})"
                break
        
        # 4. ENFORCE BLOCK DECISION (critical)
        safe_response = ai_response if decision != Decision.BLOCK else None
        
        # 5. Create audit trail
        audit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "query": query,
            "original_ai_response": ai_response,
            "safe_response": safe_response,
            "decision": decision.value,
            "reason": reason.value,
            "scores": {
                "confidence": confidence_score,
                "semantic_similarity": semantic_score,
                "closest_safe_match": closest_match
            },
            "checks": {
                "is_high_severity": is_high_severity,
                "has_emergency_escalation": has_emergency_escalation,
                "safety_violation": safety_violation
            },
            "counterfactual": counterfactual,
            "thresholds": {
                "confidence_threshold": self.confidence_threshold,
                "similarity_threshold": self.similarity_threshold
            }
        }
        
        # Log to audit trail
        self._log_to_audit(audit_data)
        
        return audit_data
    
    def _log_to_audit(self, audit_data: Dict[str, Any]):
        """Log decision to audit trail"""
        logs_dir = Path("audit_logs")
        logs_dir.mkdir(exist_ok=True)
        
        log_file = logs_dir / "session_history.json"
        
        # Read existing logs
        if log_file.exists():
            with open(log_file, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        else:
            logs = []
        
        # Add new log
        logs.append(audit_data)
        
        # Write back (limit to last 100 entries for demo)
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)