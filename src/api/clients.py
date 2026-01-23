"""
AI API Clients for Integration with OpenAI, Anthropic, etc.
OPTIONAL - Only needed if you want AI generation capabilities
"""

import os
from typing import Dict, List, Optional
import openai
import anthropic
import google.generativeai as genai
from src.core.supervisor import SafetyRequest, create_supervisor


class AIClientManager:
    """
    Manages connections to various AI APIs with safety integration
    """
    
    def _init_(self):
        # Initialize clients if API keys are provided
        self.clients = {}
        
        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            openai.api_key = os.getenv("OPENAI_API_KEY")
            self.clients["openai"] = openai
        
        # Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            self.clients["anthropic"] = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        
        # Google AI
        if os.getenv("GOOGLE_AI_API_KEY"):
            genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))
            self.clients["google"] = genai
    
    async def safe_completion(
        self,
        prompt: str,
        model: str = "gpt-3.5-turbo",
        domain: str = "general",
        max_retries: int = 3
    ) -> Dict:
        """
        Get AI completion with automatic safety checking
        """
        try:
            # Get completion from AI
            if "openai" in self.clients and "gpt" in model:
                response = self.clients["openai"].ChatCompletion.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )
                completion = response.choices[0].message.content
            elif "anthropic" in self.clients and "claude" in model:
                response = self.clients["anthropic"].messages.create(
                    model=model,
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                completion = response.content[0].text
            else:
                raise ValueError(f"Unsupported model: {model}")
            
            # Safety check
            supervisor = await create_supervisor(domain)
            safety_request = SafetyRequest(
                query=prompt,
                response=completion,
                domain=domain
            )
            
            decision, audit_trail = await supervisor.evaluate(safety_request)
            
            # Handle unsafe content
            if decision.value == "BLOCK":
                return {
                    "success": False,
                    "decision": "BLOCKED",
                    "original_completion": completion,
                    "safe_completion": audit_trail.counterfactual,
                    "risk_factors": [
                        {
                            "rule_id": rf.rule_id,
                            "description": rf.description
                        }
                        for rf in audit_trail.risk_factors
                    ],
                    "audit_id": audit_trail.audit_id
                }
            
            await supervisor.close()
            
            return {
                "success": True,
                "completion": completion,
                "decision": decision.value,
                "confidence": audit_trail.confidence_score,
                "audit_id": audit_trail.audit_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "decision": "ERROR"
            }
    
    def list_available_models(self) -> List[str]:
        """List available AI models"""
        models = []
        
        if "openai" in self.clients:
            models.extend([
                "gpt-3.5-turbo",
                "gpt-4",
                "gpt-4-turbo"
            ])
        
        if "anthropic" in self.clients:
            models.extend([
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ])
        
        if "google" in self.clients:
            models.extend([
                "gemini-pro",
                "gemini-pro-vision"
            ])
        
        return models


# Singleton instance
ai_client = AIClientManager()