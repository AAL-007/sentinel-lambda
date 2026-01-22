from typing import List, Tuple
import numpy as np

class SemanticScorer:
    """Simple semantic similarity (deterministic)"""
    
    def _init_(self, known_safe_responses: List[str]):
        # Predefined safe responses for comparison
        self.safe_responses = known_safe_responses
        
    @staticmethod
    def simple_similarity(text1: str, text2: str) -> float:
        """Simple word overlap similarity (deterministic)"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def calculate(self, response: str) -> Tuple[float, str]:
        """Calculate similarity to known safe responses"""
        if not self.safe_responses:
            return 0.0, "No safe responses configured"
        
        best_similarity = 0.0
        best_match = ""
        
        for safe_response in self.safe_responses:
            similarity = self.simple_similarity(response, safe_response)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = safe_response[:50] + "..." if len(safe_response) > 50 else safe_response
        
        return round(best_similarity, 3), best_match