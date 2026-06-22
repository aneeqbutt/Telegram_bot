# Day 1 — Implementation Reference
# Telegram News Bot | Foundation, MongoDB, Scrapers

---

## HOW TO USE THIS FILE

When the user says "using day1 create [module/phase]", follow this file exactly.
For every file you create or action you take:
- State WHAT you are creating
- State WHY you are creating it (reference the reasoning below)
- State HOW you did it (explain the key decisions made in the code)

Never skip the reasoning. Never create a file without explaining the decision behind it.

---

## PROJECT CONTEXT

Project: Telegram News Bot
Database: MongoDB Atlas (Motor async driver) — NOT Supabase
Framework: FastAPI (async)
Language: Python 3.11+
Goal for Day 1: Working folder structure + MongoDB connected + both scrapers storing articles

---

## WHY MONGODB (always explain this when setting up the DB)

- News articles are documents not rows — self-contained with title, content, metadata all in one place
- CoinTelegraph and Blockworks have different HTML structures and metadata — schema flexibility means no migrations
- Motor (async MongoDB driver) plugs directly into FastAPI's async event loop — no blocking
- MongoDB Atlas M0 is free (512MB), instant setup, no server to manage, no RLS config
- Built-in unique index handles deduplication at the DB level — no pre-check queries needed
- Native text search available for keyword classification improvements later

---

## FOLDER STRUCTURE (create exactly this)

```
TelegramBot/
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py
│   ├── cointelegraph.py
│   └── blockworks.py
├── services/
│   ├── __init__.py
│   └── scraper_service.py
├── database/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── crud.py
│   └── init_db.py
├── api/
│   ├── __init__.py
│   └── routers/
│       ├── __init__.py
│       ├── sources.py
│       ├── categories.py
│       ├── keywords.py
│       └── channels.py
├── scheduler/
│   ├── __init__.py
│   └── scheduler.py
├── utils/
│   ├── __init__.py
│   ├── config.py
│   └── logger.py
├── tests/
│   └── __init__.py
├── .env
├── requirements.txt
└── main.py
```

WHY this structure:
- Each concern lives in its own module — scraping, DB, API, scheduling never mix
- Adding a new scraper = one new file in scrapers/, zero changes elsewhere
- api/routers/ split — each entity (source, category, keyword, channel) has its own router file, clean and scalable
- tests/ ready from Day 1 — not an afterthought

---

## PHASE 1 — PROJECT SETUP (~1.5 hrs)

### requirements.txt

```
fastapi
uvicorn[standard]
motor
pymongo
httpx
beautifulsoup4
python-dotenv
pydantic
apscheduler
cloudscraper
seleniumbase
certifi
dnspython
```

WHY these packages:
- motor: async MongoDB driver, required for FastAPI async compatibility
- pymongo: motor depends on it; also used for index creation in init_db.py
- httpx: async HTTP client for scraping — Layer 1 of Cloudflare bypass system
- beautifulsoup4: HTML parsing for article content extraction
- apscheduler: hourly cron scheduler (used in Day 3, set up on Day 1)
- pydantic: data validation before any DB write — catches malformed scraper output early
- cloudscraper: Layer 2 Cloudflare bypass — spoofs Chrome TLS fingerprint, solves JS challenges
- seleniumbase: Layer 3 Cloudflare bypass — real Chrome in UC Mode, removes all bot signals at binary level
- certifi: SSL certificate bundle for MongoDB Atlas connection on Windows
- dnspython: required for mongodb+srv:// DNS resolution

---

### .env

```
MONGO_URI=mongodb+srv://<user>:<pass>@cluster0.mongodb.net/telegrambot?retryWrites=true&w=majority
DB_NAME=telegrambot
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=
AI_API_KEY=
SCRAPE_INTERVAL_MINUTES=60
MAX_RETRY_COUNT=3
LOG_LEVEL=INFO
```

WHY .env:
- All secrets in one place, never hardcoded
- python-dotenv loads this automatically on startup
- SCRAPE_INTERVAL_MINUTES and MAX_RETRY_COUNT are configurable without code changes

---

### utils/config.py

PURPOSE: Central place to load and expose all env vars. No scattered os.getenv() calls across the codebase.

HOW: Use pydantic BaseSettings or simple dataclass that reads from .env on import.
All other modules import from config.py — if a key name changes, fix it in one place only.

```python
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "telegrambot")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
AI_API_KEY = os.getenv("AI_API_KEY")
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 60))
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", 3))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

WHY central config:
- If MONGO_URI key name changes, you edit one file not 10
- Easy to add validation (assert MONGO_URI is not None) in one place
- Makes unit testing easy — mock config.py once, everything downstream uses the mock

---

### utils/logger.py

PURPOSE: Structured logger with timestamps used across all modules.

HOW: Python's built-in logging module configured once, imported everywhere.
Format: [TIMESTAMP] [LEVEL] [MODULE] message

```python
import logging
import sys
from utils.config import LOG_LEVEL

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)
    return logger
```

Usage in any module: `from utils.logger import get_logger; logger = get_logger(__name__)`

WHY logger on Day 1:
- Debugging scraper issues without logs is guesswork
- You want to see "scraped 12 articles, 3 were duplicates, 9 stored" from the very first run
- Consistent format means grep-able logs later

---

### main.py

PURPOSE: FastAPI application entry point. Mounts all routers. Connects to MongoDB on startup.

HOW: FastAPI lifespan context manager handles DB connect on startup and disconnect on shutdown.

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from database.db import connect_db, disconnect_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()

app = FastAPI(title="Telegram News Bot", lifespan=lifespan)

# Routers added Day 2
```

WHY lifespan over @app.on_event:
- on_event is deprecated in newer FastAPI versions
- Lifespan is the current recommended pattern — cleaner, explicit

---

## PHASE 2 — MONGODB SETUP (~2 hrs)

### database/db.py

PURPOSE: Single Motor client instance shared across the entire app.

HOW: Module-level client variable. connect_db() initializes it. All other modules call get_db() to get the database handle.

```python
from motor.motor_asyncio import AsyncIOMotorClient
from utils.config import MONGO_URI, DB_NAME

client: AsyncIOMotorClient = None

async def connect_db():
    global client
    client = AsyncIOMotorClient(MONGO_URI)
    # Verify connection
    await client.admin.command("ping")

async def disconnect_db():
    global client
    if client:
        client.close()

def get_db():
    return client[DB_NAME]
```

WHY single client:
- Motor clients are expensive to create — one per app, not one per request
- Connection pooling happens inside Motor automatically
- All modules call get_db() — if the connection strategy changes, fix it here only

---

### database/init_db.py

PURPOSE: Creates all collections and indexes. Run once on project setup.

HOW: Use pymongo (sync) for index creation — Motor supports it too but sync is simpler for a one-time script.

COLLECTIONS TO CREATE:
- articles
- sources
- categories
- keywords
- channels
- logs

INDEXES TO CREATE:

```
articles.url          — UNIQUE index  (deduplication — core mechanism)
articles.is_posted    — index         (dispatch query runs every hour against this)
articles.published_at — index         (time-based queries for recent articles)
articles.scraped_at   — index         (for monitoring and cleanup)
sources.base_url      — UNIQUE index  (prevent duplicate source entries)
channels.telegram_id  — UNIQUE index  (prevent duplicate channel entries)
categories.name       — UNIQUE index  (prevent duplicate categories)
logs.posted_at        — index         (dashboard history queries)
logs.article_id       — index         (look up logs by article)
```

WHY unique index on articles.url instead of pre-check:
- Pre-check = two DB round-trips (find then insert) — wasteful
- Unique index = one insert attempt, DB rejects duplicate with DuplicateKeyError
- Race-condition safe — two concurrent scrapers cannot both insert the same URL
- Faster at scale

WHY index on is_posted:
- Dispatch query is: find all articles where is_posted=false AND category is valid AND channel is active
- Without index this is a full collection scan every hour — slow as article count grows
- With index MongoDB goes directly to matching documents

SEED DATA TO INSERT after index creation:

sources collection:
```json
[
  { "name": "CoinTelegraph", "base_url": "https://cointelegraph.com", "is_active": true },
  { "name": "Blockworks", "base_url": "https://blockworks.co/news", "is_active": true }
]
```

categories collection (starter set):
```json
[
  { "name": "Bitcoin", "description": "BTC news", "is_active": true },
  { "name": "Ethereum", "description": "ETH news", "is_active": true },
  { "name": "DeFi", "description": "Decentralized finance", "is_active": true },
  { "name": "Regulation", "description": "Crypto regulation and policy", "is_active": true },
  { "name": "NFT", "description": "Non-fungible tokens", "is_active": true },
  { "name": "Uncategorized", "description": "Default fallback", "is_active": true }
]
```

keywords collection (starter set):
```json
[
  { "word": "bitcoin", "category_name": "Bitcoin", "weight": 1 },
  { "word": "btc", "category_name": "Bitcoin", "weight": 1 },
  { "word": "ethereum", "category_name": "Ethereum", "weight": 1 },
  { "word": "eth", "category_name": "Ethereum", "weight": 1 },
  { "word": "defi", "category_name": "DeFi", "weight": 1 },
  { "word": "decentralized finance", "category_name": "DeFi", "weight": 1 },
  { "word": "sec", "category_name": "Regulation", "weight": 1 },
  { "word": "regulation", "category_name": "Regulation", "weight": 1 },
  { "word": "nft", "category_name": "NFT", "weight": 1 },
  { "word": "non-fungible", "category_name": "NFT", "weight": 1 }
]
```

WHY seed on Day 1:
- Classifier (Day 2) needs keywords in the DB to function
- Scrapers need source_id to link articles to a source
- Seeding now means Day 2 is not blocked waiting for data

---

### database/models.py

PURPOSE: Pydantic models that define the exact shape of each document before DB write.

HOW: One model per collection. Used to validate scraper output before insert.

KEY MODELS:

Article (input from scraper):
```python
class ArticleCreate(BaseModel):
    url: str
    title: str
    content: str
    source_id: str
    published_at: datetime
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    is_posted: bool = False
    category: str = "Uncategorized"
    rephrased_content: Optional[str] = None
```

WHY Pydantic models:
- Catches missing or wrong-type fields from scrapers before they hit the DB
- Self-documenting — models show exactly what each collection stores
- FastAPI uses these same models for API request/response validation

---

### database/crud.py

PURPOSE: Reusable async DB helper functions. All DB operations go through here.

HOW: Functions that take a db handle and data, perform the operation, return result or raise.

KEY FUNCTIONS:

```python
async def insert_article(db, article: dict) -> str | None
    # Returns inserted _id or None if duplicate (DuplicateKeyError caught here)

async def get_unposted_articles(db) -> list
    # Returns articles where is_posted=False, category != "Uncategorized"

async def mark_article_posted(db, article_id: str)
    # Sets is_posted=True after successful Telegram post

async def get_all_sources(db) -> list
async def get_active_channels(db) -> list
async def get_keywords(db) -> list
async def insert_log(db, log: dict)
```

WHY crud.py:
- Motor queries are not written in 10 different files
- Error handling (DuplicateKeyError, connection errors) lives in one place
- Easy to add logging, metrics, or retry logic to all DB operations at once

---

## PHASE 3 — SCRAPERS (~3 hrs)

### scrapers/base_scraper.py

PURPOSE: Abstract base class with a 3-layer Cloudflare bypass system shared across all scrapers.

---

#### 3-LAYER CLOUDFLARE BYPASS SYSTEM

The core insight: news sites use varying levels of Cloudflare protection.
Instead of hardcoding one approach, base_scraper escalates through layers automatically.

```
fetch_page(url) called by any child scraper
    │
    ├─ Layer 1: httpx          → fast, async, lightweight. Works for RSS + unprotected pages.
    │           ↓ (if CF blocks with 403/503/429/520-524)
    ├─ Layer 2: cloudscraper   → spoofs Chrome TLS fingerprint, executes CF JS challenge.
    │           ↓ (if cloudscraper also fails)
    └─ Layer 3: SeleniumBase   → real Chrome in UC Mode. Removes ALL bot signals. Nuclear option.
```

Each layer only activates if the one above it fails. 99% of runs never leave Layer 1.

---

#### WHY EACH LAYER EXISTS

Layer 1 — httpx:
- Async native — plugs into FastAPI event loop without blocking
- Fast: < 1 second per request
- Works perfectly for RSS feeds and non-CF-protected pages
- Fails against Cloudflare because it has no browser fingerprint

Layer 2 — cloudscraper:
- Mimics Chrome's exact TLS cipher suites and extension order
- Executes Cloudflare's JS challenge in a sandboxed JS runtime
- Synchronous — must run in thread pool executor (run_in_executor) to avoid blocking async loop
- Fails against Cloudflare's enterprise Bot Management tier

Layer 3 — SeleniumBase UC Mode:
- Patches Chrome binary BEFORE launch — removes navigator.webdriver at source level
- Not a JS patch (which CF can detect) — it's a binary-level modification
- Spoofs: canvas fingerprint, font rendering, WebGL, plugin list, screen dimensions
- uc_gui_click_captcha() handles Turnstile CAPTCHA automatically
- Synchronous — also runs in thread pool executor
- Cost: launches a full Chrome process, ~5-10 seconds per page, high memory
- Only used when both Layer 1 and Layer 2 fail

WHY SeleniumBase over plain Playwright/Selenium:
- Plain Playwright headless: navigator.webdriver still exposed in JS
- Plain Selenium: same problem + more detectable headers
- SeleniumBase UC Mode: patches Chrome binary = undetectable at the JS level
- uc_gui_click_captcha(): automatically handles CF Turnstile without human intervention

WHY all layers run in thread pool (run_in_executor):
- FastAPI runs on asyncio — one event loop, one thread
- Blocking that thread with sync code (cloudscraper, seleniumbase) freezes the entire app
- run_in_executor() moves sync calls to worker threads, event loop stays free

---

#### CODE STRUCTURE

```python
class BaseScraper(ABC):

    async def fetch_page(self, url):
        # Layer 1: httpx — if CF blocks → call _fetch_with_cloudscraper()
        ...

    async def _fetch_with_cloudscraper(self, url):
        # Layer 2: run cloudscraper in thread pool — if fails → call _fetch_with_seleniumbase()
        ...

    def _cloudscraper_get(self, url):
        # Sync cloudscraper call — runs inside executor
        ...

    async def _fetch_with_seleniumbase(self, url):
        # Layer 3: run SeleniumBase in thread pool
        ...

    def _seleniumbase_get(self, url):
        # Sync SeleniumBase UC Mode call — runs inside executor
        # uc=True patches Chrome binary
        # uc_gui_click_captcha() handles Turnstile
        # sleep(3) waits for full JS render after CF challenge
        ...

    @abstractmethod
    async def scrape(self) -> list[dict]:
        # Child scrapers implement this
        pass
```

WHY base class (not per-scraper):
- Both scrapers share the entire bypass system — fix or upgrade once, both get it
- Adding a 4th site: inherit BaseScraper, implement scrape() — bypass system comes for free
- Single place to upgrade (e.g. add Camoufox as Layer 4 later)

---

### scrapers/cointelegraph.py

PURPOSE: Scrapes latest articles from cointelegraph.com.

HOW:
1. Fetch the listing/news page
2. Parse HTML with BeautifulSoup to find article links
3. For each article URL: fetch the article page, extract title + content + published_at
4. Return list of normalized dicts

NORMALIZED OUTPUT FORMAT (same for all scrapers):
```python
{
    "title": str,
    "url": str,           # full URL — used as dedup key
    "content": str,       # plain text, HTML stripped
    "published_at": datetime,
    "source_name": "CoinTelegraph"
}
```

WHY normalized output:
- scraper_service.py does not need to know which scraper produced the article
- Add Blockworks or any future source — service layer changes zero lines

IMPORTANT IMPLEMENTATION NOTES:
- Strip all HTML tags from content using BeautifulSoup's get_text()
- Parse timestamps to UTC datetime objects — store as datetime not string
- Limit to latest N articles per run (e.g. 10-20) — don't re-scrape full history every hour
- Log how many articles were found and how many were new vs duplicate

---

### scrapers/blockworks.py

PURPOSE: Scrapes latest articles from blockworks.co/news.

HOW: Same pattern as cointelegraph.py, different HTML selectors.

NORMALIZED OUTPUT FORMAT: Identical shape to cointelegraph.py output.

IMPORTANT IMPLEMENTATION NOTES:
- Same as CoinTelegraph — strip HTML, parse timestamps to UTC, limit articles per run
- Both scrapers MUST return exactly the same dict keys so scraper_service.py handles both identically

---

### services/scraper_service.py

PURPOSE: Orchestrates both scrapers. For each article returned: clean, validate, classify (placeholder on Day 1), store.

HOW:
1. Run CoinTelegraphScraper().scrape() and BlockworksScraper().scrape()
2. For each article dict: validate with Pydantic ArticleCreate model
3. Look up source_id from sources collection by source_name
4. Call crud.insert_article() — catch DuplicateKeyError silently, log it, continue
5. Log summary: "Scraped 20 articles, 14 new, 6 duplicates skipped"

WHY scraper_service.py orchestrates (not each scraper):
- Scrapers only know how to scrape — they don't know about the DB, models, or classification
- Single responsibility: cointelegraph.py scrapes, scraper_service.py decides what to do with output
- Easy to add a third scraper — one line added to scraper_service.py, zero changes to scrapers

WHY catch DuplicateKeyError and continue (not raise):
- Duplicates are expected and normal — especially on hourly runs where recent articles overlap
- Raising an exception would abort the entire batch because of one known-OK condition
- Log it, skip it, continue to the next article

---

## DAY 1 SUCCESS CRITERIA

At the end of Day 1, verify ALL of these before stopping:

1. `pip install -r requirements.txt` runs with no errors
2. `.env` is filled with real MONGO_URI from Atlas
3. `python database/init_db.py` runs and creates all collections + indexes in Atlas
4. Atlas UI shows: articles, sources, categories, keywords, channels, logs collections
5. Atlas UI shows: seed data in sources, categories, keywords
6. `python -c "from scrapers.cointelegraph import CoinTelegraphScraper; import asyncio; asyncio.run(CoinTelegraphScraper().scrape())"` returns article dicts
7. `python -c "from scrapers.blockworks import BlockworksScraper; import asyncio; asyncio.run(BlockworksScraper().scrape())"` returns article dicts
8. After running scraper_service: Atlas UI shows articles stored in articles collection
9. Re-running scraper_service: no new duplicates inserted (DuplicateKeyError handled, count stays same)
10. Logger output is visible and formatted correctly in terminal

---

## ENVIRONMENT VARIABLES NEEDED ON DAY 1

```
MONGO_URI         — from MongoDB Atlas connection string (required)
DB_NAME           — telegrambot (default)
LOG_LEVEL         — INFO (default)
```

These are NOT needed until Day 3:
```
TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL_ID
AI_API_KEY
```

---

## COMMON ERRORS AND FIXES

| Error | Cause | Fix |
|-------|-------|-----|
| 403 on scraper HTTP request | Missing User-Agent header | Add HEADERS dict with Mozilla UA string to all requests |
| pymongo.errors.DuplicateKeyError | Article URL already in DB | Catch in crud.insert_article(), log, return None — this is expected |
| ServerSelectionTimeoutError | Wrong MONGO_URI or IP not whitelisted | Check Atlas Network Access, whitelist your IP |
| Motor coroutine never awaited | Forgot await on Motor call | All Motor calls are async — always await them |
| datetime comparison fails | Storing timestamps as strings not datetime | Always parse to datetime object before storing |
