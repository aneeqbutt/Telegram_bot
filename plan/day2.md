# Day 2 — Implementation Reference
# Telegram News Bot | Cleaning · Classification · FastAPI · Admin Dashboard

---

## HOW TO USE THIS FILE

When the user says "using day2 create [module/phase]", follow this file exactly.
For every file you create or action you take:
- State WHAT you are creating
- State WHY you are creating it (reference the reasoning below)
- State HOW you did it (explain the key decisions made in the code)

Never skip the reasoning. Never create a file without explaining the decision behind it.

---

## CONTEXT — WHAT DAY 1 LEFT US

Day 1 delivered:
- Folder structure in place
- MongoDB Atlas connected via Motor
- All 6 collections with indexes created
- Seed data: sources, categories, keywords in DB
- CoinTelegraph + Blockworks scrapers storing raw articles

Day 2 goal: Complete Milestone 1.
Take the raw stored articles and add: cleaning, deduplication, classification, a full CRUD API, and admin dashboard.

---

## PIPELINE AFTER DAY 2

```
Scrapers (Day 1)
  → clean_article()          [NEW - Phase 1]
  → dedup check              [NEW - Phase 1]
  → classify_article()       [NEW - Phase 2]
  → MongoDB insert (Day 1)
  → FastAPI endpoints        [NEW - Phase 3]
  → Admin dashboard          [NEW - Phase 4]
```

---

## PHASE 1 — DATA CLEANING & NORMALIZATION (~1 hr)

### utils/cleaner.py

PURPOSE: Single module that applies all cleaning rules to raw scraper output. Every article passes through this before Pydantic validation or DB insert.

WHY a dedicated cleaner module:
- Scrapers do basic HTML stripping but inconsistently between sources
- A dedicated cleaner applies identical rules to every article regardless of origin
- When a cleaning rule changes (e.g. strip emojis), edit one file — not every scraper

HOW to implement:

```python
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import timezone
import re


def clean_html(text: str) -> str:
    """Strip all HTML tags, collapse whitespace, remove special chars."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    clean = soup.get_text(separator=" ")
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def normalize_timestamp(raw) -> datetime:
    """Parse any timestamp format to UTC datetime object."""
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc).replace(tzinfo=None)
    try:
        dt = dateparser.parse(str(raw))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def normalize_url(url: str) -> str:
    """Strip query params, fragments, trailing slashes. Lowercase."""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url.lower().strip())
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', '', ''))
    return clean


def clean_article(article: dict) -> dict:
    """Run all cleaners on a raw scraper output dict. Returns cleaned dict."""
    return {
        **article,
        "url": normalize_url(article.get("url", "")),
        "title": article.get("title", "").strip(),
        "content": clean_html(article.get("content", "")),
        "published_at": normalize_timestamp(article.get("published_at")),
    }
```

WHY normalize_url() is critical for dedup:
- Same article can appear as /article/123 and /article/123?ref=twitter
- The MongoDB unique index on url would treat these as different documents
- Stripping query params before insert ensures the index correctly catches duplicates

WHY parse timestamp to UTC datetime not string:
- MongoDB sorts datetime objects correctly — strings sort lexicographically (broken)
- Comparison queries like "articles since yesterday" only work with datetime objects
- TTL indexes (auto-delete old articles) require datetime type

---

### Scraper-level dedup in scraper_service.py

Add a fast pre-check before classification and DB insert:

```python
async def article_exists(db, url: str) -> bool:
    doc = await db["articles"].find_one({"url": url}, {"_id": 1})
    return doc is not None
```

WHY check before classify, not just rely on DB unique index:
- The DB unique index is the hard guard (always keep it)
- But classifying an article that's already stored wastes time
- In Day 3, it would also waste an AI API call per duplicate
- Pre-check costs one fast indexed lookup — worth it

---

## PHASE 2 — CLASSIFICATION SYSTEM (~1.5 hrs)

### services/classifier.py

PURPOSE: Assigns a category to every article based on keyword matching against the keywords collection.

WHY keyword matching not ML:
- Transparent and admin-controllable — admin adds "solana" → DeFi and it works instantly
- No training data, no model hosting, no API cost
- Admin can tune results in real time via the dashboard
- Simple to debug — if an article is miscategorized, you can see exactly which keywords matched

HOW the classifier works:

```python
from utils.logger import get_logger

logger = get_logger(__name__)

# In-memory keyword cache
_keyword_map: dict[str, str] = {}  # { word: category_name }


async def load_keywords(db):
    """Load all keywords from MongoDB into memory. Call on startup and after keyword changes."""
    global _keyword_map
    keywords = await db["keywords"].find({}).to_list(length=None)
    _keyword_map = {kw["word"].lower(): kw["category_name"] for kw in keywords}
    logger.info(f"Loaded {len(_keyword_map)} keywords into classifier cache")


async def reload_keywords(db):
    """Refresh keyword cache. Called when admin adds/removes keywords via API."""
    await load_keywords(db)


def classify_article(title: str, content: str) -> str:
    """
    Match article title + content against keyword map.
    Title matches count double (stronger signal).
    Returns best matching category name or 'Uncategorized'.
    """
    if not _keyword_map:
        return "Uncategorized"

    # Title weighted 2x — a keyword in the title = article is primarily about it
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
```

WHY in-memory cache:
- Loading keywords from MongoDB on every article classification = DB query per article per run
- With 20 articles per scrape run every hour = 480 unnecessary DB queries per day
- Cache once at startup, reload only when admin changes keywords via the dashboard

WHY title * 2:
- "Bitcoin ETF approved" → title mentions bitcoin, body may discuss ETF mechanics
- Title is the strongest signal of what the article is about
- Doubling title in the search string gives title matches double the score naturally

HOW to wire into scraper_service.py:

```python
# In scraper_service.py, after cleaning, before DB insert:
from services.classifier import classify_article

cleaned = clean_article(raw_article)
category = classify_article(cleaned["title"], cleaned["content"])
cleaned["category"] = category
# Then insert to DB
```

HOW to load on startup in main.py:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    db = get_db()
    await load_keywords(db)   # Load classifier cache on startup
    yield
    await disconnect_db()
```

---

## PHASE 3 — FASTAPI CRUD ENDPOINTS (~2 hrs)

### Structure

```
api/
└── routers/
    ├── sources.py
    ├── categories.py
    ├── keywords.py
    ├── channels.py
    └── articles.py
```

### Design rules for all routers

1. Routers call crud.py functions only — no raw Motor queries inside routers
2. All routes use Depends(get_db) for the Motor db handle
3. All mounted under /api/v1/ prefix in main.py
4. Return 404 if document not found, 409 on duplicate key

WHY Depends(get_db):
- FastAPI dependency injection — db handle passed into each route cleanly
- Easy to mock in tests — swap get_db() for a test DB in test config
- No global Motor state floating around in router files

WHY /api/v1/ prefix:
- Versioning from day one
- If you break the API later, add /api/v2/ — v1 clients keep working
- Cost to add now: zero. Cost to add later: painful

---

### api/routers/sources.py

```python
from fastapi import APIRouter, Depends, HTTPException
from database.db import get_db
from database import crud

router = APIRouter(prefix="/sources", tags=["Sources"])

@router.get("/")
async def list_sources(db=Depends(get_db)):
    return await crud.get_all_sources(db)

@router.post("/")
async def add_source(data: dict, db=Depends(get_db)):
    return await crud.insert_source(db, data)

@router.put("/{source_id}")
async def update_source(source_id: str, data: dict, db=Depends(get_db)):
    updated = await crud.update_source(db, source_id, data)
    if not updated:
        raise HTTPException(404, "Source not found")
    return updated

@router.delete("/{source_id}")
async def delete_source(source_id: str, db=Depends(get_db)):
    await crud.delete_source(db, source_id)
    return {"deleted": source_id}
```

Apply the same pattern for: categories.py, channels.py

---

### api/routers/keywords.py

IMPORTANT: After any write operation, reload the classifier cache.

```python
from services.classifier import reload_keywords

@router.post("/")
async def add_keyword(data: dict, db=Depends(get_db)):
    result = await crud.insert_keyword(db, data)
    await reload_keywords(db)   # Refresh classifier immediately
    return result

@router.delete("/{keyword_id}")
async def delete_keyword(keyword_id: str, db=Depends(get_db)):
    await crud.delete_keyword(db, keyword_id)
    await reload_keywords(db)   # Refresh classifier immediately
    return {"deleted": keyword_id}
```

WHY reload after keyword change:
- The classifier uses an in-memory cache
- Without reload, new keywords only take effect after server restart
- This makes the system truly dynamic — admin adds keyword, next scrape run uses it

---

### api/routers/articles.py — READ ONLY

```python
router = APIRouter(prefix="/articles", tags=["Articles"])

@router.get("/")
async def list_articles(
    skip: int = 0,
    limit: int = 20,
    category: str = None,
    is_posted: bool = None,
    db=Depends(get_db)
):
    return await crud.get_articles(db, skip=skip, limit=limit, category=category, is_posted=is_posted)

@router.get("/{article_id}")
async def get_article(article_id: str, db=Depends(get_db)):
    article = await crud.get_article_by_id(db, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article
```

WHY articles are read-only via API:
- Articles are owned by the scraper pipeline
- Allowing API writes creates a second code path that bypasses cleaning and classification
- If you need to correct an article, do it via a dedicated admin action — not a generic PUT

WHY pagination (skip + limit):
- Collection grows every hour — listing all articles without pagination will eventually timeout
- Index on scraped_at means sorted pages are fast

---

### main.py — Mount all routers

```python
from api.routers import sources, categories, keywords, channels, articles

app.include_router(sources.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(keywords.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
```

Verify all endpoints appear at: http://localhost:8000/docs

---

## PHASE 4 — ADMIN DASHBOARD (~2 hrs)

### Stack choice: Jinja2 server-rendered HTML

WHY Jinja2 not React:
- Zero build step — no npm, no webpack, no CORS config
- FastAPI has first-class Jinja2 support built in
- Admin tool used by one person — does not need SPA complexity
- Fast to build, easy to read, easy to maintain

### Setup in main.py

```python
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
```

### Folder structure

```
templates/
├── base.html           # Shared layout: navbar, sidebar, CSS link
├── sources.html
├── categories.html
├── keywords.html
├── channels.html
└── articles.html
static/
└── style.css           # Minimal table/form/badge styles
```

WHY base.html:
- Navbar and sidebar defined once — change the nav in one place, all pages update
- Consistent layout and styles without copy-pasting

---

### api/routers/dashboard.py

PURPOSE: GET routes that render Jinja2 templates. Separate from the JSON API routers.

```python
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from database.db import get_db
from database import crud

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")

@router.get("/sources")
async def sources_page(request: Request, db=Depends(get_db)):
    sources = await crud.get_all_sources(db)
    return templates.TemplateResponse("sources.html", {"request": request, "sources": sources})

@router.get("/articles")
async def articles_page(request: Request, skip: int = 0, category: str = None, db=Depends(get_db)):
    articles = await crud.get_articles(db, skip=skip, limit=20, category=category)
    categories = await crud.get_all_categories(db)
    return templates.TemplateResponse("articles.html", {
        "request": request,
        "articles": articles,
        "categories": categories,
        "current_category": category
    })
```

WHY dashboard routes call the same crud.py functions as the API:
- No duplicate DB logic
- Dashboard and API always return the same data
- One place to fix a query bug

---

### templates/base.html (structure)

```html
<!DOCTYPE html>
<html>
<head>
  <title>Telegram News Bot — Admin</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav>
    <a href="/dashboard/sources">Sources</a>
    <a href="/dashboard/categories">Categories</a>
    <a href="/dashboard/keywords">Keywords</a>
    <a href="/dashboard/channels">Channels</a>
    <a href="/dashboard/articles">Articles</a>
  </nav>
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

---

### Dashboard pages — what each page must show

sources.html:
- Table: name | base_url | active status | actions
- Form: add new source (name + url)
- Toggle button: activate / deactivate source

categories.html:
- Table: name | description | active | article count
- Form: add new category
- Toggle: activate / deactivate

keywords.html:
- Table: word | category | actions
- Filter: dropdown to show keywords by category
- Form: add new keyword (word + category dropdown)
- Delete button per keyword

channels.html:
- Table: name | telegram_id | active | post interval
- Form: add new channel
- Toggle: activate / deactivate

articles.html:
- Table: title | source | category | published_at | is_posted badge
- Filter: by category (dropdown), by is_posted (checkbox)
- Pagination: prev/next buttons using skip param
- is_posted badge: green "Posted" / grey "Pending"

---

## NEW DEPENDENCIES FOR DAY 2

```
jinja2
python-multipart
python-dateutil
```

Add to requirements.txt.

pip install jinja2 python-multipart python-dateutil

---

## UPDATED CRUD FUNCTIONS NEEDED (database/crud.py additions)

Day 1 crud.py had: insert_article, get_unposted_articles, mark_article_posted

Day 2 needs these added:

```python
# Sources
async def get_all_sources(db) -> list
async def insert_source(db, data: dict) -> dict
async def update_source(db, source_id: str, data: dict) -> dict | None
async def delete_source(db, source_id: str)

# Categories
async def get_all_categories(db) -> list
async def insert_category(db, data: dict) -> dict
async def update_category(db, category_id: str, data: dict) -> dict | None
async def delete_category(db, category_id: str)

# Keywords
async def get_all_keywords(db, category: str = None) -> list
async def insert_keyword(db, data: dict) -> dict
async def delete_keyword(db, keyword_id: str)

# Channels
async def get_active_channels(db) -> list
async def get_all_channels(db) -> list
async def insert_channel(db, data: dict) -> dict
async def update_channel(db, channel_id: str, data: dict) -> dict | None
async def delete_channel(db, channel_id: str)

# Articles
async def get_articles(db, skip=0, limit=20, category=None, is_posted=None) -> list
async def get_article_by_id(db, article_id: str) -> dict | None
```

WHY expand crud.py not write Motor queries in routers:
- All DB access stays in one file
- Routers stay thin and readable
- If MongoDB collection names change, fix in crud.py only

---

## DAY 2 SUCCESS CRITERIA — MILESTONE 1 COMPLETE

Verify ALL of these before ending Day 2:

1. Run scraper_service.py — check MongoDB Atlas: content field has no HTML tags
2. Re-run scraper_service.py — article count in Atlas does not grow (dedup working)
3. Every article document in Atlas has a category field that is not null or empty
4. At least some articles have category != "Uncategorized" (keyword matching working)
5. http://localhost:8000/docs — all 16+ endpoints visible and returning correct responses
6. POST a new keyword via /api/v1/keywords — run scraper again — new articles use updated category
7. PUT a source is_active=false via API — scraper skips that source on next run
8. http://localhost:8000/dashboard/articles — shows paginated article list
9. Dashboard keywords page — add a new keyword — classifier reloads without server restart
10. Dashboard articles page — category filter works correctly

---

## COMMON ERRORS AND FIXES — DAY 2

| Error | Cause | Fix |
|-------|-------|-----|
| HTML still in content after cleaning | Scraper not calling clean_article() | Wire clean_article() in scraper_service.py before insert |
| All articles are "Uncategorized" | Classifier cache not loaded on startup | Call load_keywords(db) in lifespan startup block |
| New keyword not affecting classification | reload_keywords() not called after insert | Add await reload_keywords(db) in keyword POST/DELETE routes |
| Jinja2 TemplateNotFound error | templates/ folder not found | Confirm directory="templates" path is relative to where uvicorn runs |
| 422 Unprocessable Entity on API POST | Pydantic model mismatch | Check request body matches the expected model fields |
| Dashboard forms not submitting | Missing python-multipart | pip install python-multipart — required for form data in FastAPI |
| Duplicate category error on seed re-run | init_db.py inserting duplicates | Use update_one with upsert=True in seed script instead of insert_many |
