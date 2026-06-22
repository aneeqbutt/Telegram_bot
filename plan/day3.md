# Day 3 — Implementation Reference
# Telegram News Bot | AI Rewriter · Telegram Poster · Dispatcher · Scheduler

---

## HOW TO USE THIS FILE

When the user says "using day3 create [module/phase]", follow this file exactly.
For every file you create or action you take:
- State WHAT you are creating
- State WHY you are creating it (reference the reasoning below)
- State HOW you did it (explain the key decisions made in the code)

Never skip the reasoning. Never create a file without explaining the decision behind it.

---

## CONTEXT — WHAT DAYS 1 AND 2 LEFT US

Day 1 delivered:
- MongoDB Atlas connected, all 6 collections with indexes
- CoinTelegraph scraper (RSS + httpx Layer 1, full article content)
- Blockworks scraper (direct /api/posts JSON endpoint, no Cloudflare friction)
- Articles stored and deduplicated in MongoDB

Day 2 delivered:
- utils/cleaner.py — strips HTML, normalizes URLs and timestamps
- services/classifier.py — keyword-based category assignment with in-memory cache
- Full FastAPI CRUD API for all collections
- Admin dashboard via Jinja2

Day 3 goal: Make the bot actually post.
Take classified articles from MongoDB, rewrite them with AI, send to Telegram, run the full cycle automatically on a schedule.

---

## PIPELINE AFTER DAY 3

```
APScheduler tick (every N minutes)
  → run_scrapers()           [Day 1 + 2]
       → clean_article()     [Day 2]
       → classify_article()  [Day 2]
       → MongoDB insert       [Day 1]
  → dispatch_articles()      [NEW - Phase 3]
       → get_unposted_articles()
       → rewrite_article()   [NEW - Phase 1]
       → format_message()    [NEW - Phase 2]
       → send_to_telegram()  [NEW - Phase 2]
       → mark_article_posted()
       → insert_log()
```

---

## PHASE 1 — AI REWRITER (~1.5 hrs)

### services/ai_rewriter.py

PURPOSE: Takes a raw article (title + content) and returns a shorter, punchy rewritten version optimized for Telegram.

WHY rewrite instead of posting raw content:
- Raw article content is 2,000–19,000 chars — way too long for a Telegram post
- Telegram messages have a 4,096 char limit
- A rewritten summary is more engaging for channel subscribers
- Consistent voice and format across all posts regardless of source

WHY Google Gemini Flash (free tier):
- 1,500 requests/day free with no credit card
- gemini-2.0-flash model is fast (~2-3 seconds per request)
- Large context window — handles long Blockworks articles (19,000 chars) in one call
- API is REST-based — use httpx (already installed), no extra SDK needed
- If user has a different AI key, the prompt and structure stay the same — just swap the endpoint

HOW to call the Gemini API:

```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={AI_API_KEY}

Body:
{
  "contents": [
    { "parts": [ { "text": "<full prompt here>" } ] }
  ]
}

Response:
{
  "candidates": [
    { "content": { "parts": [ { "text": "<rewritten article>" } ] } }
  ]
}
```

THE PROMPT (use exactly this, it produces clean Telegram-ready output):

```
You are a crypto news editor for a Telegram channel. Rewrite the article below into a punchy 3-5 sentence summary.

Rules:
- Start with the most important fact
- No clickbait, no filler phrases ("In this article...", "According to...")
- Plain text only — no markdown, no bullet points
- End with one sentence on why this matters for crypto investors
- Maximum 800 characters

Title: {title}

Article:
{content}
```

WHY these prompt rules:
- "Start with the most important fact" → avoids buried lede
- "No markdown" → Telegram will handle formatting via parse_mode — don't double-format
- "Maximum 800 characters" → leaves room for the title, source, and URL in the final message
- "Why this matters" → adds value beyond just summarizing

HOW to implement with fallback:

```python
import httpx
from utils.config import AI_API_KEY
from utils.logger import get_logger

logger = get_logger("ai_rewriter")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

PROMPT_TEMPLATE = """You are a crypto news editor for a Telegram channel. Rewrite the article below into a punchy 3-5 sentence summary.

Rules:
- Start with the most important fact
- No clickbait, no filler phrases ("In this article...", "According to...")
- Plain text only — no markdown, no bullet points
- End with one sentence on why this matters for crypto investors
- Maximum 800 characters

Title: {title}

Article:
{content}"""


async def rewrite_article(title: str, content: str) -> str:
    """
    Calls Gemini API to rewrite article into a short Telegram summary.
    Falls back to a truncated version of the original content on failure.
    """
    if not AI_API_KEY:
        logger.warning("AI_API_KEY not set — using content truncation fallback")
        return _truncate_fallback(content)

    prompt = PROMPT_TEMPLATE.format(title=title, content=content[:6000])

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GEMINI_URL,
                params={"key": AI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            response.raise_for_status()
            data = response.json()
            rewritten = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.info(f"AI rewrite successful: {len(rewritten)} chars for '{title[:50]}'")
            return rewritten
    except Exception as e:
        logger.warning(f"AI rewrite failed for '{title[:50]}': {e} — using truncation fallback")
        return _truncate_fallback(content)


def _truncate_fallback(content: str, max_chars: int = 800) -> str:
    """
    When AI is unavailable: return first 800 chars of cleaned content.
    Cuts at the last full sentence within the limit.
    """
    if len(content) <= max_chars:
        return content
    truncated = content[:max_chars]
    last_period = truncated.rfind('.')
    if last_period > max_chars // 2:
        return truncated[:last_period + 1]
    return truncated.rstrip() + "..."
```

WHY fallback to truncation not silence:
- AI API rate limits, network errors, or key expiry should not silently kill the posting pipeline
- A truncated post is better than no post
- The fallback is logged so the admin knows the AI failed

WHY content[:6000] before sending to AI:
- Gemini Flash has a large context but long prompts are slower and cost more tokens
- First 6,000 chars captures the full article body for any article in the system
- Anything beyond 6,000 chars is usually boilerplate, related links, or author bios

---

## PHASE 2 — TELEGRAM POSTER (~1.5 hrs)

### services/telegram_poster.py

PURPOSE: Formats the rewritten article into a Telegram message and sends it to the channel via Bot API.

WHY use raw httpx not python-telegram-bot library:
- python-telegram-bot adds 15+ dependencies and a complex async wrapper
- The Bot API is simple REST — one endpoint, one POST, one response
- httpx is already installed and used across the project
- Fewer dependencies = fewer breakage points

HOW the Telegram Bot API sendMessage works:

```
POST https://api.telegram.org/bot{TOKEN}/sendMessage

Body:
{
  "chat_id": "@yourchannel",
  "text": "message text here",
  "parse_mode": "HTML",
  "disable_web_page_preview": false
}

Success response: { "ok": true, "result": { "message_id": 123 } }
Error response:   { "ok": false, "error_code": 429, "description": "Too Many Requests: retry after 30" }
```

MESSAGE FORMAT (use exactly this template):

```
📰 <b>{title}</b>

{rewritten_content}

🔗 <a href="{url}">Read full article</a>
📌 Source: {source_name} | 🏷 {category}
```

WHY HTML parse_mode not MarkdownV2:
- MarkdownV2 requires escaping 18+ special characters (., !, -, etc.)
- Crypto article titles contain all of them: "Bitcoin hits $100K — ETF approved!"
- HTML parse_mode only needs &amp; &lt; &gt; escaped — much cleaner
- Easier to debug when something breaks

WHY include the source URL:
- Telegram channels build trust by linking to sources
- Users can verify the news and read the full article
- Boosts engagement — "Read full article" links drive traffic

HOW to implement with retry on rate limit:

```python
import httpx
import asyncio
from utils.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from utils.logger import get_logger

logger = get_logger("telegram_poster")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

MESSAGE_TEMPLATE = """📰 <b>{title}</b>

{content}

🔗 <a href="{url}">Read full article</a>
📌 Source: {source_name} | 🏷 {category}"""


def _escape_html(text: str) -> str:
    """Escape characters that break Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(title: str, content: str, url: str, source_name: str, category: str) -> str:
    return MESSAGE_TEMPLATE.format(
        title=_escape_html(title),
        content=_escape_html(content),
        url=url,
        source_name=_escape_html(source_name),
        category=_escape_html(category)
    )


async def send_message(text: str, retries: int = 3) -> dict:
    """
    Sends a message to the configured Telegram channel.
    Retries on rate limit (429) with the retry_after delay from the API response.
    Returns the message result dict on success, raises on final failure.
    """
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
                data = response.json()

            if data.get("ok"):
                logger.info(f"Message sent successfully (message_id: {data['result']['message_id']})")
                return data["result"]

            error_code = data.get("error_code")
            description = data.get("description", "")

            if error_code == 429:
                # Rate limited — Telegram tells us exactly how long to wait
                retry_after = int(description.split("retry after ")[-1]) if "retry after" in description else 30
                logger.warning(f"Telegram rate limit hit — waiting {retry_after}s before retry {attempt}/{retries}")
                await asyncio.sleep(retry_after)
                continue

            raise Exception(f"Telegram API error {error_code}: {description}")

        except httpx.TimeoutException:
            logger.warning(f"Telegram request timed out (attempt {attempt}/{retries})")
            if attempt < retries:
                await asyncio.sleep(5)
            else:
                raise

    raise Exception(f"Failed to send Telegram message after {retries} attempts")
```

WHY retry on 429 specifically (not all errors):
- 429 is rate limiting — always temporary, always recoverable
- The API tells you exactly how many seconds to wait via the description field
- Other errors (400 bad request, 401 unauthorized) are not recoverable by retrying
- Retrying a 400 just wastes time and API calls

WHY disable_web_page_preview: False:
- Telegram generates a link preview for the article URL
- This shows the article's thumbnail image in the channel post
- Makes posts more visually engaging with no extra code

---

## PHASE 3 — DISPATCHER (~1 hr)

### services/dispatcher.py

PURPOSE: Connects everything together. Fetches unposted articles → rewrites each → posts to Telegram → marks as posted → logs.

WHY a separate dispatcher (not inline in scraper_service):
- scraper_service.py does one job: scrape and store
- dispatcher.py does one job: read stored articles and post them
- Keeping them separate means you can run scraping without posting (debug mode)
- You can also run just the dispatcher to clear a posting backlog

HOW the dispatcher flow works:

```python
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
            # 1. Rewrite content with AI
            rewritten = await rewrite_article(article["title"], article["content"])

            # 2. Format the Telegram message
            message = format_message(
                title=article["title"],
                content=rewritten,
                url=article["url"],
                source_name=article.get("source_name", "Unknown"),
                category=article.get("category", "Uncategorized")
            )

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
                "source_id": article.get("source_id")
            })

            posted += 1

            # Respect Telegram's rate limit: 1 message per second for channels
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Failed to dispatch article '{article.get('title', '')[:50]}': {e}")
            failed += 1
            continue

    logger.info(f"Dispatch complete: {posted} posted, {failed} failed")
    return {"posted": posted, "failed": failed}
```

WHY sleep(1) between posts:
- Telegram limits channel bots to 1 message/second per chat
- Without sleep: second message gets a 429 rate limit error
- sleep(1) is the simplest correct rate limit compliance

WHY continue on failure (not raise):
- One bad article (bad URL, malformed title) should not block the rest of the queue
- The failed article stays is_posted=False — it will be retried on the next dispatch run
- The error is logged for visibility

WHY log to MongoDB (not just print):
- The admin dashboard can query logs to show posting history
- You can see exactly which articles were posted, when, and the Telegram message_id
- If a post is wrong, you have the message_id to delete it via the Bot API

---

## PHASE 4 — APSCHEDULER WIRING (~1 hr)

### scheduler/scheduler.py

PURPOSE: Runs the full scrape → classify → post cycle automatically on the configured interval.

WHY APScheduler over cron / Celery / RQ:
- APScheduler runs inside the FastAPI process — no second process to manage
- No Redis, no worker queue, no broker — zero extra infrastructure
- Interval-based jobs restart automatically on server restart
- SCRAPE_INTERVAL_MINUTES is already in .env — APScheduler reads it directly

WHY AsyncIOScheduler (not BackgroundScheduler):
- FastAPI runs on asyncio
- AsyncIOScheduler runs jobs in the same event loop — can await Motor and httpx calls directly
- BackgroundScheduler runs in a thread — async jobs in a thread pool cause coroutine never awaited errors

HOW to implement:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.config import SCRAPE_INTERVAL_MINUTES
from utils.logger import get_logger

logger = get_logger("scheduler")
scheduler = AsyncIOScheduler()


async def scheduled_run():
    """
    Full pipeline run: scrape → classify → store → dispatch.
    Called by APScheduler on the configured interval.
    """
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
```

WHY import run_scrapers and dispatch_articles inside scheduled_run not at module top:
- Circular import risk: scheduler → scraper_service → db → scheduler
- Late import (inside the function) breaks the circular chain
- Functions are only called at runtime, not at import time

HOW to wire into main.py lifespan:

```python
from scheduler.scheduler import start_scheduler, stop_scheduler
from services.classifier import load_keywords

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    db = get_db()
    await load_keywords(db)    # Load classifier cache before scheduler starts
    start_scheduler()          # Start scheduled cycle
    yield
    stop_scheduler()           # Stop scheduler on shutdown
    await disconnect_db()
```

WHY load_keywords() before start_scheduler():
- The scheduler's first run happens after SCRAPE_INTERVAL_MINUTES — but if you trigger manually, classify_article() needs the cache already loaded
- If cache is empty on first run, all articles get "Uncategorized" and never get dispatched

---

## PHASE 5 — ADMIN TRIGGER ENDPOINT (~30 mins)

### api/routers/admin.py

PURPOSE: Manual trigger for scraping and dispatching without waiting for the scheduler tick.

WHY a manual trigger:
- During development and testing you don't want to wait 60 minutes for the scheduler
- Admins can force a scrape after adding a new source or keyword
- POST /api/v1/admin/run-now triggers the full pipeline immediately

```python
from fastapi import APIRouter, BackgroundTasks
from database.db import get_db
from services.scraper_service import run_scrapers
from services.dispatcher import dispatch_articles

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/run-now")
async def trigger_run(background_tasks: BackgroundTasks):
    """Triggers a full scrape + dispatch cycle immediately in the background."""
    background_tasks.add_task(_run_pipeline)
    return {"status": "Pipeline triggered", "message": "Running in background — check logs"}


async def _run_pipeline():
    from utils.logger import get_logger
    logger = get_logger("admin")
    db = get_db()
    scrape_result = await run_scrapers()
    dispatch_result = await dispatch_articles(db)
    logger.info(f"Manual trigger complete: scrape={scrape_result}, dispatch={dispatch_result}")
```

WHY BackgroundTasks not direct await:
- The scrape + dispatch cycle takes 30-120 seconds for 80 articles
- A direct await would leave the HTTP connection open the whole time
- BackgroundTasks returns the 200 immediately, runs the cycle in background
- Logs show the result when it finishes

---

## NEW FILES CREATED ON DAY 3

```
services/
├── ai_rewriter.py       [NEW]
├── telegram_poster.py   [NEW]
└── dispatcher.py        [NEW]
scheduler/
└── scheduler.py         [NEW]
api/routers/
└── admin.py             [NEW]
```

Updated files:
```
main.py                  — add scheduler start/stop to lifespan, mount admin router
utils/config.py          — confirm TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, AI_API_KEY loaded
```

---

## ENVIRONMENT VARIABLES NEEDED FOR DAY 3

All must be set in .env before Day 3 runs:

```
TELEGRAM_BOT_TOKEN     — from @BotFather on Telegram
TELEGRAM_CHANNEL_ID    — @yourchannel or -100xxxxxxxxxx (numeric ID)
AI_API_KEY             — Gemini API key from aistudio.google.com
SCRAPE_INTERVAL_MINUTES — 60 (default)
```

HOW to get TELEGRAM_CHANNEL_ID:
- If the channel is public: use @channelname directly
- If private: forward any message from the channel to @userinfobot — it returns the numeric ID

HOW to get Gemini API key:
- Go to aistudio.google.com
- Click "Get API Key" → create key
- Free tier: 1,500 requests/day, 15 requests/minute

---

## UPDATED CRUD FUNCTIONS NEEDED (database/crud.py additions)

Day 3 needs these added to crud.py:

```python
async def get_unposted_articles(db) -> list
    # Already exists from Day 1 — confirm it filters category != "Uncategorized"
    # If not, update the query:
    # db.articles.find({"is_posted": False, "category": {"$ne": "Uncategorized"}})

async def mark_article_posted(db, article_id: str)
    # Already exists from Day 1

async def insert_log(db, log: dict)
    # Already exists from Day 1
```

No new crud functions needed — Day 1 already provided the required operations.

---

## DAY 3 SUCCESS CRITERIA

Verify ALL of these before ending Day 3:

1. Set TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, AI_API_KEY in .env
2. python -c "from services.ai_rewriter import rewrite_article; import asyncio; print(asyncio.run(rewrite_article('Test', 'Bitcoin hits 100k')))" — prints a rewritten summary
3. POST /api/v1/admin/run-now — returns immediately, logs show scrape + dispatch completing
4. Telegram channel shows a new post with correct title, summary, source link, and category
5. Check MongoDB: article is_posted=True after post
6. Check MongoDB logs collection: entry with telegram_message_id exists
7. Re-run pipeline — duplicate articles are NOT posted again (is_posted guard works)
8. Turn off AI_API_KEY temporarily — fallback truncation still posts without crashing
9. uvicorn main:app — scheduler starts, logs "Running every 60 minutes"
10. Wait one scheduler tick — new articles appear in Telegram automatically without any manual trigger

---

## COMMON ERRORS AND FIXES — DAY 3

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized from Telegram | Wrong BOT_TOKEN | Re-copy token from @BotFather — no spaces |
| 400 Bad Request: chat not found | Wrong CHANNEL_ID | Check channel ID with @userinfobot |
| 400 Bad Request: can't parse entities | Unescaped HTML in message | Run all text fields through _escape_html() before inserting into template |
| 429 Too Many Requests from Telegram | Posting too fast | sleep(1) between posts — already in dispatcher.py |
| 403 Forbidden from Telegram | Bot is not admin of the channel | Go to channel → Admins → add your bot |
| Gemini 429 rate limit | > 15 requests/minute free tier | Dispatcher already has sleep(1) — adds 1s between AI calls naturally |
| Scheduler not running | start_scheduler() not in lifespan | Confirm start_scheduler() is called before yield in lifespan |
| Articles with Uncategorized never posted | get_unposted_articles filters them out | Add more keywords for the categories or handle Uncategorized as a valid post category |
| AsyncIOScheduler not found | apscheduler not installed | pip install apscheduler |
