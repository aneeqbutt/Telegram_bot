# All database operations for the project live here.
# Every router and service calls these functions instead of writing Motor queries directly.
# This keeps raw DB logic in one place so errors, retries, or collection name changes
# only need to be fixed once.

from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from utils.logger import get_logger

logger = get_logger("crud")


# ── Articles ──────────────────────────────────────────────────────────────────

async def insert_article(db, article: dict) -> str | None:
    # Inserts a new article. Returns the inserted _id as a string, or None if the URL already exists.
    try:
        result = await db.articles.insert_one(article)
        return str(result.inserted_id)
    except DuplicateKeyError:
        logger.info(f"Skipped duplicate article: {article.get('url')}")
        return None
    except Exception as e:
        logger.error(f"Error inserting article: {e}")
        return None


async def article_exists(db, url: str) -> bool:
    # Returns True if an article with this URL is already in the database.
    doc = await db.articles.find_one({"url": url}, {"_id": 1})
    return doc is not None


async def get_unposted_articles(db) -> list:
    # Returns all articles that haven't been posted yet and have a real category assigned.
    cursor = db.articles.find({
        "is_posted": False,
        "category": {"$ne": "Uncategorized"}
    })
    return await cursor.to_list(length=None)


async def mark_article_posted(db, article_id: str):
    # Flips is_posted to True after the article has been sent to Telegram.
    try:
        await db.articles.update_one(
            {"_id": ObjectId(article_id)},
            {"$set": {"is_posted": True}}
        )
    except Exception as e:
        logger.error(f"Error marking article {article_id} as posted: {e}")


async def get_articles(db, skip=0, limit=20, category=None, is_posted=None) -> list:
    # Returns a paginated list of articles, optionally filtered by category and/or posted status.
    query = {}
    if category:
        query["category"] = category
    if is_posted is not None:
        query["is_posted"] = is_posted
    cursor = db.articles.find(query).skip(skip).limit(limit)
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def get_article_by_id(db, article_id: str) -> dict | None:
    # Fetches a single article by its MongoDB _id. Returns None if not found or ID is invalid.
    try:
        doc = await db.articles.find_one({"_id": ObjectId(article_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception:
        return None


# ── Sources ───────────────────────────────────────────────────────────────────

async def get_all_sources(db) -> list:
    # Returns all source documents with _id converted to string.
    cursor = db.sources.find()
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def get_source_by_id(db, source_id: str) -> dict | None:
    # Fetches a single source by its _id. Returns None if not found or ID is invalid.
    try:
        doc = await db.sources.find_one({"_id": ObjectId(source_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception:
        return None


async def insert_source(db, data: dict) -> dict:
    # Inserts a new source and returns the document with the new _id attached.
    result = await db.sources.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data


async def update_source(db, source_id: str, data: dict) -> dict | None:
    # Updates the given fields on a source and returns the updated document.
    update_data = {k: v for k, v in data.items() if v is not None}
    if not update_data:
        doc = await db.sources.find_one({"_id": ObjectId(source_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    await db.sources.update_one({"_id": ObjectId(source_id)}, {"$set": update_data})
    doc = await db.sources.find_one({"_id": ObjectId(source_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def delete_source(db, source_id: str):
    # Deletes a source by its _id.
    await db.sources.delete_one({"_id": ObjectId(source_id)})


# ── Categories ────────────────────────────────────────────────────────────────

async def get_all_categories(db) -> list:
    # Returns all category documents with _id converted to string.
    cursor = db.categories.find()
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def insert_category(db, data: dict) -> dict:
    # Inserts a new category and returns the document with the new _id attached.
    result = await db.categories.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data


async def update_category(db, category_id: str, data: dict) -> dict | None:
    # Updates the given fields on a category and returns the updated document.
    update_data = {k: v for k, v in data.items() if v is not None}
    if not update_data:
        doc = await db.categories.find_one({"_id": ObjectId(category_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    await db.categories.update_one({"_id": ObjectId(category_id)}, {"$set": update_data})
    doc = await db.categories.find_one({"_id": ObjectId(category_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def delete_category(db, category_id: str):
    # Deletes a category by its _id.
    await db.categories.delete_one({"_id": ObjectId(category_id)})


# ── Keywords ──────────────────────────────────────────────────────────────────

async def get_all_keywords(db, category: str = None) -> list:
    # Returns all keywords, optionally filtered to a specific category name.
    query = {}
    if category:
        query["category_name"] = category
    cursor = db.keywords.find(query)
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def get_keywords(db) -> list:
    # Returns all keywords with no filtering (used by the classifier loader).
    cursor = db.keywords.find()
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def insert_keyword(db, data: dict) -> dict:
    # Inserts a new keyword and returns the document with the new _id attached.
    result = await db.keywords.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data


async def delete_keyword(db, keyword_id: str):
    # Deletes a keyword by its _id.
    await db.keywords.delete_one({"_id": ObjectId(keyword_id)})


# ── Channels ──────────────────────────────────────────────────────────────────

async def get_all_channels(db) -> list:
    # Returns all channel documents with _id converted to string.
    cursor = db.channels.find()
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def get_active_channels(db) -> list:
    # Returns only channels with is_active=True (used by the dispatcher).
    cursor = db.channels.find({"is_active": True})
    results = await cursor.to_list(length=None)
    for r in results:
        r["_id"] = str(r["_id"])
    return results


async def insert_channel(db, data: dict) -> dict:
    # Inserts a new channel and returns the document with the new _id attached.
    result = await db.channels.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data


async def update_channel(db, channel_id: str, data: dict) -> dict | None:
    # Updates the given fields on a channel and returns the updated document.
    update_data = {k: v for k, v in data.items() if v is not None}
    if not update_data:
        doc = await db.channels.find_one({"_id": ObjectId(channel_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    await db.channels.update_one({"_id": ObjectId(channel_id)}, {"$set": update_data})
    doc = await db.channels.find_one({"_id": ObjectId(channel_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def delete_channel(db, channel_id: str):
    # Deletes a channel by its _id.
    await db.channels.delete_one({"_id": ObjectId(channel_id)})


# ── Logs ──────────────────────────────────────────────────────────────────────

async def insert_log(db, log: dict):
    # Writes a posting log entry (article_id, telegram_message_id, posted_at, etc.) to the logs collection.
    try:
        await db.logs.insert_one(log)
    except Exception as e:
        logger.error(f"Error inserting log: {e}")
