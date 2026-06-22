# Admin router — exposes a manual trigger for the full scrape + dispatch pipeline.
# Returns 200 immediately and runs the pipeline in the background via FastAPI BackgroundTasks
# so the HTTP connection is not held open for the 30-120 seconds the pipeline takes.

from fastapi import APIRouter, BackgroundTasks
from database.db import get_db
from utils.logger import get_logger

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/run-now")
async def trigger_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_pipeline)
    return {"status": "Pipeline triggered", "message": "Running in background — check logs"}


async def _run_pipeline():
    logger = get_logger("admin")
    try:
        from services.scraper_service import run_scrapers
        from services.dispatcher import dispatch_articles
        db = get_db()
        scrape_result = await run_scrapers()
        dispatch_result = await dispatch_articles(db)
        logger.info(f"Manual trigger complete: scrape={scrape_result}, dispatch={dispatch_result}")
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}", exc_info=True)
