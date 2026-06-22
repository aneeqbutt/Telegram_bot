# Dispatcher — the bridge between MongoDB and Telegram.
# Reads every unposted article that has a real category, rewrites it with AI,
# formats it into a Telegram message, sends it, then marks it posted in MongoDB.
# Runs once per scheduler tick and once on every admin "Run Now" trigger.

import asyncio
from datetime import datetime
from database import crud
from services.ai_rewriter import rewrite_article
from services.telegram_poster import format_message, send_message
from utils.logger import get_logger

logger = get_logger("dispatcher")


async def dispatch_articles(db) -> dict:
    articles = await crud.get_unposted_articles(db)

    if not articles:
        logger.info("No unposted articles to dispatch")
        return {"posted": 0, "failed": 0}

    logger.info(f"Dispatching {len(articles)} unposted articles...")

    posted = 0
    failed = 0

    for article in articles:
        try:
            # Fix 2: content guard — skip articles with no usable content before hitting the AI
            if not article.get("content") or len(article["content"]) < 50:
                logger.warning(f"Skipping '{article.get('title', '')[:50]}' — content too short")
                failed += 1
                continue

            # Resolve source name from source_id
            source_name = "Unknown"
            if article.get("source_id"):
                source = await crud.get_source_by_id(db, str(article["source_id"]))
                if source:
                    source_name = source.get("name", "Unknown")

            # 1. Rewrite content with AI
            rewritten = await rewrite_article(article["title"], article["content"])

            # 2. Format the Telegram message
            title = article["title"]
            url = article["url"]
            category = article.get("category", "Uncategorized")

            message = format_message(
                title=title,
                content=rewritten,
                url=url,
                source_name=source_name,
                category=category
            )

            # Fix 3: message length guard — Telegram hard-limits messages to 4096 chars
            if len(message) > 4096:
                overage = len(message) - 4096
                rewritten = rewritten[:len(rewritten) - overage - 10] + "..."
                message = format_message(title, rewritten, url, source_name, category)

            # 3. Send to Telegram
            result = await send_message(message)

            # 4. Mark article as posted in MongoDB
            await crud.mark_article_posted(db, str(article["_id"]))

            # 5. Write to logs collection
            await crud.insert_log(db, {
                "article_id": str(article["_id"]),
                "telegram_message_id": result.get("message_id"),
                "posted_at": datetime.utcnow(),
                "category": article.get("category"),
                "source_id": str(article.get("source_id", ""))
            })

            posted += 1
            logger.info(f"Posted: '{article['title'][:60]}'")

            # Respect Telegram's 1 msg/sec channel rate limit
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Failed to dispatch '{article.get('title', '')[:50]}': {e}")
            failed += 1
            continue

    logger.info(f"Dispatch complete: {posted} posted, {failed} failed")
    return {"posted": posted, "failed": failed}
