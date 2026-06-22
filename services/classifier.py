# Keyword-based article classifier.
# Loads keywords from MongoDB into memory on startup and uses them to assign
# a category to every article. The in-memory cache means no DB query per article.
# The cache is refreshed instantly whenever an admin adds or removes a keyword via the API.

from utils.logger import get_logger

logger = get_logger(__name__)

# In-memory map of { keyword_word: category_name } — loaded from MongoDB on startup
_keyword_map: dict[str, str] = {}


async def load_keywords(db):
    # Pulls all keywords from MongoDB and rebuilds the in-memory cache.
    # Called once on app startup and again after any keyword change.
    global _keyword_map
    try:
        keywords = await db["keywords"].find({}).to_list(length=None)
        _keyword_map = {kw["word"].lower(): kw["category_name"] for kw in keywords}
        logger.info(f"Loaded {len(_keyword_map)} keywords into classifier cache")
    except Exception as e:
        logger.error(f"Error loading keywords into classifier cache: {e}")


async def reload_keywords(db):
    # Refreshes the keyword cache — called by the keywords router after any add or delete.
    await load_keywords(db)


def classify_article(title: str, content: str) -> str:
    # Scores the article against every keyword. Title is weighted 2x over body content.
    # Returns the category with the highest score, or "Uncategorized" if nothing matches.
    if not _keyword_map:
        return "Uncategorized"

    # Concatenate title twice so title keyword hits count double
    search_text = (title.lower() + " ") * 2 + content.lower()

    scores: dict[str, int] = {}
    for word, category in _keyword_map.items():
        if word in search_text:
            scores[category] = scores.get(category, 0) + 1

    if not scores:
        return "Uncategorized"

    best = max(scores, key=scores.get)
    logger.debug(f"Classified '{title[:50]}' → {best} (scores: {scores})")
    return best
