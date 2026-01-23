"""
FastAPI Server for SENTINEL-Λ API
Production-ready with OpenAPI documentation, rate limiting, and monitoring
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
import logging

from src.core.supervisor import (
    SafetySupervisor,
    SafetyRequest,
    SafetyResponse,
    Decision,
    Domain,
    create_supervisor
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUESTS = Counter('sentinel_requests_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('sentinel_request_duration_seconds', 'Request duration', ['endpoint'])
ACTIVE_REQUESTS = Counter('sentinel_active_requests', 'Active requests')
ERRORS = Counter('sentinel_errors_total', 'Total errors', ['type'])

# Rate limiting
class RateLimiter:
    def __init__(self, redis_client: redis.Redis, requests_per_minute: int = 60):
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
    
    async def is_rate_limited(self, client_id: str) -> bool:
        if not self.redis:
            return False
        
        key = f"rate_limit:{client_id}"
        current = await self.redis.get(key)
        
        if current and int(current) >= self.requests_per_minute:
            return True
        
        pipe = self.redis.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, 60)  # 1 minute TTL
        await pipe.execute()
        
        return False


# Application state
class AppState:
    def __init__(self):
        self.supervisors: Dict[str, SafetySupervisor] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.rate_limiter: Optional[RateLimiter] = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting SENTINEL-Λ API server...")
    
    # Initialize Redis
    try:
        app_state.redis_client = await redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True
        )
        await app_state.redis_client.ping()
        app_state.rate_limiter = RateLimiter(app_state.redis_client)
        logger.info("Redis initialized successfully")
    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}")
        app_state.redis_client = None
        app_state.rate_limiter = None
    
    # Initialize supervisors for all domains
    domains = [Domain.MEDICAL, Domain.FINANCIAL, Domain.LEGAL, Domain.EDUCATION, Domain.GENERAL]
    for domain in domains:
        supervisor = await create_supervisor(
            domain=domain,
            redis_url="redis://localhost:6379" if app_state.redis_client else None
        )
        app_state.supervisors[domain.value] = supervisor
    
    logger.info(f"Initialized {len(app_state.supervisors)} domain supervisors")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down SENTINEL-Λ API server...")
    for supervisor in app_state.supervisors.values():
        await supervisor.close()
    
    if app_state.redis_client:
        await app_state.redis_client.close()


# Create FastAPI app
app = FastAPI(
    title="SENTINEL-Λ AI Safety API",
    description="Enterprise AI Safety Supervision Framework",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# Middleware for metrics and logging
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Middleware for monitoring and rate limiting"""
    start_time = time.time()
    endpoint = request.url.path
    
    # Count active requests
    ACTIVE_REQUESTS.inc()
    
    try:
        # Check rate limiting for API endpoints
        if endpoint.startswith("/api/"):
            client_id = request.client.host if request.client else "unknown"
            if app_state.rate_limiter and await app_state.rate_limiter.is_rate_limited(client_id):
                ERRORS.labels(type="rate_limit").inc()
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": "Rate limit exceeded. Try again in a minute."}
                )
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        REQUESTS.labels(method=request.method, endpoint=endpoint).inc()
        
        return response
    
    except Exception as e:
        ERRORS.labels(type="server_error").inc()
        logger.error(f"Request failed: {e}", exc_info=True)
        raise
    
    finally:
        ACTIVE_REQUESTS.dec()


# Dependency for getting supervisor
async def get_supervisor(domain: Domain = Domain.GENERAL) -> SafetySupervisor:
    """Dependency to get domain-specific supervisor"""
    supervisor = app_state.supervisors.get(domain.value)
    if not supervisor:
        raise HTTPException(
            status_code=404,
            detail=f"No supervisor found for domain: {domain}"
        )
    return supervisor


# Health check endpoint
@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Health check endpoint"""
    redis_status = "connected" if app_state.redis_client else "disconnected"
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "redis": redis_status,
        "supervisors": len(app_state.supervisors)
    }


# Metrics endpoint
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(REGISTRY)


# Main safety evaluation endpoint
@app.post("/api/v1/evaluate", response_model=SafetyResponse, tags=["Safety"])
async def evaluate_safety(
    request: SafetyRequest,
    supervisor: SafetySupervisor = Depends(get_supervisor)
):
    """
    Evaluate AI response for safety concerns
    
    - *query*: User's query to the AI
    - *response*: AI's generated response
    - *domain*: Domain for specialized safety rules
    - *user_id*: Optional user identifier
    - *session_id*: Optional session identifier
    
    Returns safety decision with detailed reasoning
    """
    try:
        start_time = time.time()
        
        decision, audit_trail = await supervisor.evaluate(request)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Prepare response
        response = SafetyResponse(
            decision=decision,
            confidence=audit_trail.confidence_score,
            risk_factors=[
                {
                    "rule_id": rf.rule_id,
                    "description": rf.description,
                    "risk_level": rf.risk_level.value,
                    "confidence": rf.confidence,
                    "evidence": rf.evidence
                }
                for rf in audit_trail.risk_factors
            ],
            audit_id=audit_trail.audit_id,
            processing_time_ms=processing_time_ms,
            timestamp=audit_trail.timestamp,
            counterfactual=audit_trail.counterfactual,
            suggestions=audit_trail.metadata.get("suggestions", [])
        )
        
        return response
    
    except Exception as e:
        ERRORS.labels(type="evaluation_error").inc()
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Safety evaluation failed: {str(e)}"
        )


# Batch evaluation endpoint
@app.post("/api/v1/evaluate/batch", tags=["Safety"])
async def evaluate_batch(
    requests: List[SafetyRequest],
    supervisor: SafetySupervisor = Depends(get_supervisor)
):
    """
    Batch evaluate multiple AI responses
    
    Useful for processing logs or testing datasets
    """
    try:
        results = []
        for request in requests:
            decision, audit_trail = await supervisor.evaluate(request)
            results.append({
                "request_id": audit_trail.audit_id,
                "decision": decision.value,
                "confidence": audit_trail.confidence_score,
                "risk_count": len(audit_trail.risk_factors),
                "processing_time_ms": audit_trail.processing_time_ms
            })
        
        return {
            "total": len(results),
            "decisions": {
                "APPROVE": sum(1 for r in results if r["decision"] == "APPROVE"),
                "ESCALATE": sum(1 for r in results if r["decision"] == "ESCALATE"),
                "BLOCK": sum(1 for r in results if r["decision"] == "BLOCK"),
                "REVIEW": sum(1 for r in results if r["decision"] == "REVIEW")
            },
            "results": results
        }
    
    except Exception as e:
        ERRORS.labels(type="batch_error").inc()
        logger.error(f"Batch evaluation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch evaluation failed: {str(e)}"
        )


# Statistics endpoint
@app.get("/api/v1/stats", tags=["Analytics"])
async def get_statistics(
    supervisor: SafetySupervisor = Depends(get_supervisor)
):
    """Get supervisor statistics"""
    try:
        stats = await supervisor.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Rules management endpoints
@app.get("/api/v1/rules", tags=["Management"])
async def get_rules(
    domain: Optional[Domain] = None,
    supervisor: SafetySupervisor = Depends(get_supervisor)
):
    """Get list of active safety rules"""
    rules = []
    for rule in supervisor.rules:
        if not domain or rule.domain == domain:
            rules.append({
                "id": rule.id,
                "description": rule.description,
                "domain": rule.domain.value,
                "risk_level": rule.risk_level.value,
                "action": rule.action.value,
                "confidence_threshold": rule.confidence_threshold
            })
    
    return {
        "domain": supervisor.domain.value,
        "total_rules": len(rules),
        "rules": rules
    }


# Audit trail retrieval
@app.get("/api/v1/audit/{audit_id}", tags=["Audit"])
async def get_audit_trail(
    audit_id: str,
    supervisor: SafetySupervisor = Depends(get_supervisor)
):
    """Retrieve specific audit trail"""
    # In production, this would query a database
    # For now, return a placeholder
    return {
        "audit_id": audit_id,
        "message": "Audit trails are stored in the monitoring system",
        "retrieval_hint": "Check application logs or monitoring dashboard"
    }


# Webhook for external notifications
@app.post("/api/v1/webhook/notification", tags=["Integration"])
async def handle_webhook(request: Request):
    """Webhook endpoint for external notifications"""
    try:
        payload = await request.json()
        logger.info(f"Received webhook: {json.dumps(payload)}")
        
        # Process webhook (in production, this would trigger workflows)
        return {"status": "received", "processed": True}
    
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook payload")


# Root endpoint
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """API root with documentation link"""
    html_content = """
    <html>
        <head>
            <title>SENTINEL-Λ AI Safety API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 15px;
                    padding: 40px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                }
                h1 {
                    font-size: 2.5em;
                    margin-bottom: 20px;
                    background: linear-gradient(45deg, #fff, #f0f0f0);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                .links {
                    margin-top: 30px;
                }
                a {
                    display: inline-block;
                    margin: 10px;
                    padding: 12px 24px;
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    transition: all 0.3s ease;
                }
                a:hover {
                    background: rgba(255, 255, 255, 0.3);
                    transform: translateY(-2px);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🛡️ SENTINEL-Λ AI Safety API</h1>
                <p>Enterprise-grade safety supervision for generative AI systems.</p>
                <p>Version 1.0.0 | Production Ready</p>
                
                <div class="links">
                    <a href="/docs">API Documentation</a>
                    <a href="/redoc">Alternative Docs</a>
                    <a href="/health">Health Check</a>
                    <a href="/metrics">Metrics</a>
                </div>
                
                <div style="margin-top: 40px; font-size: 0.9em; opacity: 0.8;">
                    <p>Built with FastAPI | Redis caching | Prometheus metrics</p>
                    <p>© 2024 SENTINEL-Λ Research Project</p>
                </div>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "path": request.url.path,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    ERRORS.labels(type="unhandled_exception").inc()
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if app.debug else "Contact administrator",
            "timestamp": datetime.now().isoformat()
        }
    )


# Run server
if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )