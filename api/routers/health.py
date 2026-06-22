# Health check router — returns the live status of MongoDB and the scheduler.
# Used to confirm the app is fully operational after startup or deployment.

from fastapi import APIRouter
from database.db import get_db
from scheduler.scheduler import scheduler

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    status = {"status": "ok", "mongodb": "unknown", "scheduler": "unknown"}

    try:
        db = get_db()
        await db.command("ping")
        status["mongodb"] = "connected"
    except Exception as e:
        status["mongodb"] = f"error: {str(e)}"
        status["status"] = "degraded"

    status["scheduler"] = "running" if scheduler.running else "stopped"
    if not scheduler.running:
        status["status"] = "degraded"

    return status
