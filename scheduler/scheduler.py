# Scheduler — runs the full scrape + dispatch pipeline automatically on a fixed interval.
# Uses AsyncIOScheduler (not BackgroundScheduler) because Motor and httpx are async —
# running them in a background thread causes "coroutine never awaited" errors.
# Imports inside scheduled_run() to avoid circular imports at module load time.
# Any exception inside a tick is caught and logged — the scheduler always continues to the next tick.

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.config import SCRAPE_INTERVAL_MINUTES
from utils.logger import get_logger

logger = get_logger("scheduler")
scheduler = AsyncIOScheduler()


async def scheduled_run():
    # Imports are inside the function to avoid circular imports at module load time
    try:
        from database.db import get_db
        from services.scraper_service import run_scrapers
        from services.dispatcher import dispatch_articles

        logger.info("=== Scheduled run starting ===")
        db = get_db()

        scrape_result = await run_scrapers()
        logger.info(f"Scrape result: {scrape_result}")

        dispatch_result = await dispatch_articles(db)
        logger.info(f"Dispatch result: {dispatch_result}")

        logger.info("=== Scheduled run complete ===")

    except Exception as e:
        # Log but never re-raise — scheduler must continue to next tick even on failure
        logger.error(f"=== Scheduled run FAILED: {e} ===", exc_info=True)


def start_scheduler():
    scheduler.add_job(
        scheduled_run,
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        id="scrape_and_dispatch",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started — running every {SCRAPE_INTERVAL_MINUTES} minutes")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
