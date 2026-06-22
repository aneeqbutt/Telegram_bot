# Scraper orchestrator — the main pipeline that runs on every scheduled tick.
# Runs both scrapers concurrently, then for each article: cleans the raw text,
# checks for duplicates, classifies by keyword, validates with Pydantic, and stores in MongoDB.

import asyncio
from datetime import datetime
from utils.logger import get_logger
from database.db import get_db
from database.models import ArticleCreate
from database import crud
from utils.cleaner import clean_article
from services.classifier import classify_article
from scrapers.cointelegraph import CoinTelegraphScraper
from scrapers.blockworks import BlockworksScraper

logger = get_logger("scraper_service")


async def run_scrapers(limit_per_source: int = 10):
    # Runs CoinTelegraph and Blockworks scrapers in parallel, then processes every article
    # through the clean → dedup → classify → validate → store pipeline.
    logger.info("Initializing scraper service run...")
    db = get_db()

    # Reload the keyword cache so the classifier is up to date for this run
    from services.classifier import load_keywords
    await load_keywords(db)

    # Load only active sources so disabled sources are automatically skipped
    logger.info("Loading active sources from database...")
    sources = await db.sources.find({"is_active": True}).to_list(length=None)

    source_map = {}
    for s in sources:
        source_map[s["name"]] = str(s["_id"])

    if not source_map:
        logger.error("No active sources found in database. Did you run init_db.py?")
        return

    # Run both scrapers at the same time to cut total fetch time roughly in half
    coin_scraper = CoinTelegraphScraper()
    block_scraper = BlockworksScraper()

    logger.info("Running scrapers concurrently...")
    results = await asyncio.gather(
        coin_scraper.scrape(),
        block_scraper.scrape(),
        return_exceptions=True  # One scraper failing won't crash the other
    )

    scraped_articles = []

    if isinstance(results[0], Exception):
        logger.error(f"CoinTelegraphScraper failed with exception: {results[0]}")
    else:
        scraped_articles.extend(results[0])

    if isinstance(results[1], Exception):
        logger.error(f"BlockworksScraper failed with exception: {results[1]}")
    else:
        scraped_articles.extend(results[1])

    logger.info(f"Total articles fetched from scrapers: {len(scraped_articles)}")

    new_count = 0
    duplicate_count = 0
    error_count = 0

    for art in scraped_articles:
        source_name = art.get("source_name")
        source_id = source_map.get(source_name)

        if not source_id:
            logger.error(f"Source ID not found for {source_name}. Skipping article...")
            error_count += 1
            continue

        # Strip HTML, normalize URL and timestamp
        cleaned_art = clean_article(art)

        # Fast pre-check: skip before classification and validation if URL already stored
        if await crud.article_exists(db, cleaned_art["url"]):
            logger.debug(f"DUPLICATE [{cleaned_art['source_name']}] {cleaned_art['title'][:60]}...")
            duplicate_count += 1
            continue

        # Assign a category based on keyword matching
        category = classify_article(cleaned_art["title"], cleaned_art["content"])

        # Validate the article shape with Pydantic before writing to DB
        try:
            article_data = ArticleCreate(
                url=cleaned_art["url"],
                title=cleaned_art["title"],
                content=cleaned_art["content"],
                source_id=source_id,
                published_at=cleaned_art["published_at"],
                scraped_at=datetime.utcnow(),
                is_posted=False,
                category=category
            )
        except Exception as e:
            logger.error(f"Pydantic validation failed for article '{cleaned_art.get('title')}': {e}")
            error_count += 1
            continue

        # Insert — the unique index on url is the final duplicate guard
        article_dict = article_data.model_dump()
        inserted_id = await crud.insert_article(db, article_dict)
        if inserted_id:
            logger.debug(f"STORED [{cleaned_art['source_name']}] {cleaned_art['title'][:60]}...")
            new_count += 1
        else:
            logger.debug(f"DUPLICATE (DB Index) [{cleaned_art['source_name']}] {cleaned_art['title'][:60]}...")
            duplicate_count += 1

    logger.info(f"Scraper run completed: {new_count} new, {duplicate_count} duplicates skipped, {error_count} validation errors.")
    return {
        "new": new_count,
        "duplicates": duplicate_count,
        "errors": error_count
    }


if __name__ == "__main__":
    # Allows running the pipeline directly from the terminal for testing
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    async def main():
        from database.db import connect_db, disconnect_db
        try:
            await connect_db()
            await run_scrapers()
        except Exception as e:
            logger.error(f"Runner execution failed: {e}")
        finally:
            await disconnect_db()

    asyncio.run(main())
