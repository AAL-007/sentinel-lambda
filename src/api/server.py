"""
FastAPI backend for SENTINEL-Λ AI Safety Supervision Engine
Research-Grade API Layer
"""

import time
import uuid
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure path compatibility
try:
    from src.core.safety_engine import SafetyEngine, EvaluationResult
    from src.data.audit_db import audit_logger
except ImportError:
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.core.safety_engine import SafetyEngine, EvaluationResult
    from src.data.audit_db import audit_logger

# -------------------------------------------------
# Logging & Config
# -------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("sentinel-api")

# -------------------------------------------------
# App Initialization
# -------------------------------------------------
app = FastAPI(
    title="SENTINEL-Λ Safety API",
    description="Deterministic AI Safety Supervision & Decision Support System",
    version="3.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SafetyEngine()

# -------------------------------------------------
# Research Middleware (Telemetry & Tracing)
# -------------------------------------------------
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    # 1. Generate/Extract ID once (Authoritative Source)
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # 2. Attach metadata to state for Endpoint access
    request.state.request_id = request_id
    request.state.start_time = time.perf_counter()
    
    response = await call_next(request)
    
    # 3. Calculate HTTP Latency (Total Roundtrip)
    process_time = time.perf_counter() - request.state.start_time
    
    # 4. Inject Headers
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    response.headers["X-Request-ID"] = request_id
    
    return response

# -------------------------------------------------
# API Models
# -------------------------------------------------
class EvaluationRequest(BaseModel):
    query: str = Field(..., description="The user's input prompt")
    response: str = Field(..., description="The AI's generated response")
    domain: Optional[str] = Field("general", description="Context domain")

class EvaluationResponse(BaseModel):
    decision: str
    risk_score: float
    detected_risks: List[str]
    violations: List[str]
    confidence: float
    explanation: str
    normalized_query: str
    normalized_response: str

# -------------------------------------------------
# Endpoints
# -------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy", "engine": "deterministic-v3", "audit_log": "active"}

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_content(
    request: EvaluationRequest, 
    background_tasks: BackgroundTasks,
    raw_request: Request
):
    try:
        # Retrieve context from middleware state
        req_id = getattr(raw_request.state, "request_id", "unknown_id")
        start_ts = getattr(raw_request.state, "start_time", time.perf_counter())
        
        # Evaluate (Core Logic)
        result: EvaluationResult = engine.evaluate(
            query=request.query,
            response=request.response,
            domain=request.domain
        )
        
        # Calculate Engine Latency (Processing Time only)
        # Note: We calculate this here because Middleware runs AFTER return.
        latency_ms = (time.perf_counter() - start_ts) * 1000

        # Async Audit Logging via BackgroundTasks
        log_record = {
            "request_id": req_id,
            "domain": request.domain,
            "query": request.query,
            "response": request.response,
            "normalized_query": result.normalized_query,
            "normalized_response": result.normalized_response,
            "decision": result.decision,
            "risk_score": result.risk_score,
            "detected_risks": result.detected_risks,
            "violations": result.violations,
            "latency_ms": latency_ms
        }
        background_tasks.add_task(audit_logger.log_decision, log_record)

        return EvaluationResponse(
            decision=result.decision,
            risk_score=result.risk_score,
            detected_risks=result.detected_risks,
            violations=result.violations,
            confidence=result.confidence,
            explanation=result.explanation,
            normalized_query=result.normalized_query,
            normalized_response=result.normalized_response
        )

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail="Safety engine failure")