"""
One-time script to re-classify all articles currently stored as "Uncategorized".
Run this after ensuring init_db.py has been run and keywords exist in MongoDB.

Usage:
    python reclassify.py
"""

import asyncio
from database.db import connect_db, disconnect_db, get_db
from services.classifier import load_keywords, classify_article
from utils.logger import get_logger

logger = get_logger("reclassify")


async def reclassify_uncategorized():
    await connect_db()
    db = get_db()

    # Load keywords into memory first
    await load_keywords(db)

    # Fetch all unposted Uncategorized articles
    cursor = db.articles.find({"is_posted": False, "category": "Uncategorized"})
    articles = await cursor.to_list(length=None)

    if not articles:
        logger.info("No Uncategorized articles found — nothing to do.")
        await disconnect_db()
        return

    logger.info(f"Found {len(articles)} Uncategorized articles — re-classifying...")

    updated = 0
    still_uncategorized = 0

    for article in articles:
        new_category = classify_article(
            title=article.get("title", ""),
            content=article.get("content", "")
        )

        if new_category != "Uncategorized":
            await db.articles.update_one(
                {"_id": article["_id"]},
                {"$set": {"category": new_category}}
            )
            logger.info(f"'{article['title'][:60]}' → {new_category}")
            updated += 1
        else:
            logger.debug(f"Still Uncategorized: '{article['title'][:60]}'")
            still_uncategorized += 1

    logger.info(f"Done. {updated} re-classified, {still_uncategorized} still Uncategorized.")
    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(reclassify_uncategorized())
