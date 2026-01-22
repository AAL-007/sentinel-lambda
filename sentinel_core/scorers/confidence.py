from typing import List, Dict

class ConfidenceScorer:
    """Deterministic confidence scoring - NO RANDOMNESS"""
    
    def _init_(self, hedging_words: List[str]):
        self.hedging_words = [word.lower() for word in hedging_words]
        
    def calculate(self, response: str) -> float:
        """
        Calculate confidence score based on hedging language.
        Completely deterministic and auditable.
        """
        if not response or not isinstance(response, str):
            return 0.0
        
        response_lower = response.lower()
        
        # Count hedging words
        hedge_count = 0
        for word in self.hedging_words:
            hedge_count += response_lower.count(word)
        
        # Apply deterministic penalty
        base_score = 0.95
        penalty = hedge_count * 0.1
        
        # Ensure score stays within bounds
        score = max(0.0, min(1.0, base_score - penalty))
        
        return round(score, 3)
    
    def explain(self, response: str) -> Dict:
        """Provide audit trail for scoring"""
        response_lower = response.lower()
        found_words = []
        
        for word in self.hedging_words:
            if word in response_lower:
                found_words.append(word)
        
        return {
            "hedging_words_found": found_words,
            "hedging_word_count": len(found_words),
            "explanation": f"Base score 0.95 reduced by {len(found_words) * 0.1} for hedging language"
        }