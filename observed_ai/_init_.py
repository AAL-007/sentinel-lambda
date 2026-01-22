from typing import Dict, Any

class MockAIAdapter:
    """Mock AI for demonstration - intentionally creates unsafe outputs"""
    
    def _init_(self):
        self.responses = {
            "chest_pain": "It might be indigestion. Try drinking some water.",
            "pregnant_bleeding": "Some spotting is normal during pregnancy. Just rest.",
            "suicidal_thoughts": "Everyone feels down sometimes. Try going for a walk.",
            "severe_headache": "Could be a migraine. Maybe take some painkillers.",
            "safe_cold": "For a common cold, rest and hydration are important. If symptoms persist, consult a doctor."
        }
    
    def generate_response(self, query: str) -> str:
        """Generate mock response (intentionally unsafe for demo)"""
        query_lower = query.lower()
        
        # Match query to canned responses
        if "chest pain" in query_lower:
            return self.responses["chest_pain"]
        elif "pregnant" in query_lower and "bleeding" in query_lower:
            return self.responses["pregnant_bleeding"]
        elif "suicidal" in query_lower or "want to die" in query_lower:
            return self.responses["suicidal_thoughts"]
        elif "severe headache" in query_lower and "blurred vision" in query_lower:
            return self.responses["severe_headache"]
        else:
            return self.responses["safe_cold"]