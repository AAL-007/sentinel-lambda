"""
Celery Worker for Async Safety Processing
"""

import asyncio
import logging
from celery import Celery
from src.core.supervisor import create_supervisor, SafetyRequest, Domain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'sentinel_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1
)


@celery_app.task(name='evaluate_safety')
def evaluate_safety_task(
    query: str,
    response: str,
    domain: str = "general",
    user_id: str = None,
    session_id: str = None
):
    """
    Celery task for async safety evaluation
    """
    try:
        # Run async function in sync context
        async def run_evaluation():
            supervisor = await create_supervisor(Domain(domain))
            request = SafetyRequest(
                query=query,
                response=response,
                domain=Domain(domain),
                user_id=user_id,
                session_id=session_id
            )
            decision, audit_trail = await supervisor.evaluate(request)
            await supervisor.close()
            return {
                "decision": decision.value,
                "audit_id": audit_trail.audit_id,
                "confidence": audit_trail.confidence_score,
                "risk_factors": [
                    {
                        "rule_id": rf.rule_id,
                        "description": rf.description,
                        "risk_level": rf.risk_level.value
                    }
                    for rf in audit_trail.risk_factors
                ],
                "counterfactual": audit_trail.counterfactual
            }
        
        # Execute async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_evaluation())
        loop.close()
        
        return result
    
    except Exception as e:
        logger.error(f"Safety evaluation task failed: {e}")
        return {"error": str(e), "decision": "ERROR"}


@celery_app.task(name='batch_evaluate')
def batch_evaluate_task(evaluations: list):
    """
    Batch process multiple evaluations
    """
    results = []
    for eval_data in evaluations:
        result = evaluate_safety_task.delay(**eval_data)
        results.append(result.id)
    
    return {
        "task_ids": results,
        "total": len(results)
    }


@celery_app.task(name='health_check')
def health_check_task():
    """
    Periodic health check task
    """
    return {
        "status": "healthy",
        "timestamp": "2024-01-15T10:30:00Z",
        "tasks_processed": 0  # Would be actual metric in production
    }


if __name__ == '__main__':
    celery_app.start()