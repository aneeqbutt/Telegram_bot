# Day 4 — Implementation Reference
# Telegram News Bot | Testing · Error Hardening · Health Check · Deployment

---

## HOW TO USE THIS FILE

When the user says "using day4 create [module/phase]", follow this file exactly.
For every file you create or action you take:
- State WHAT you are creating
- State WHY you are creating it (reference the reasoning below)
- State HOW you did it (explain the key decisions made in the code)

Never skip the reasoning. Never create a file without explaining the decision behind it.

---

## CONTEXT — WHAT DAYS 1, 2, AND 3 LEFT US

Day 1 delivered: Scrapers, MongoDB Atlas, deduplication
Day 2 delivered: Cleaner, classifier, FastAPI CRUD API, admin dashboard
Day 3 delivered: AI rewriter, Telegram poster, dispatcher, APScheduler

Day 4 goal: Make the bot production-grade.
The pipeline works end-to-end but has no tests, no systematic error handling, no health visibility, and no deployment process. Day 4 hardens everything so the bot can run unattended without manual babysitting.

---

## WHAT "PRODUCTION-GRADE" MEANS FOR THIS BOT

A bot that:
1. Never crashes silently — all failures are logged with enough detail to diagnose
2. Recovers from transient errors (network blip, rate limit) without human intervention
3. Has a health endpoint so you can tell at a glance whether it's alive
4. Can be verified correct with a test suite before deployment
5. Runs continuously without needing a terminal window open

---

## PHASE 1 — TEST SUITE (~2.5 hrs)

### Testing philosophy for this project

WHY test at all:
- Scrapers, classifiers, and posters all interact with external systems
- Without tests, changing one thing (e.g. updating the AI prompt) can silently break another
- Tests are the only way to verify the duplicate guard, fallback logic, and message formatter work correctly without sending test Telegrams or hitting live APIs

WHY pytest not unittest:
- Less boilerplate — no TestCase classes, no setUp/tearDown verbosity
- pytest fixtures are cleaner than setUp
- pytest-asyncio handles async test functions natively
- Industry standard for Python projects

WHY mock external calls:
- Tests must not hit live APIs (Telegram, Gemini, MongoDB Atlas)
- A test that hits the real Telegram API is slow, costs API calls, and fails when offline
- pytest-mock / unittest.mock patches the external call with a controlled response

---

### tests/conftest.py

PURPOSE: Shared fixtures used across all test files — mock DB, sample article data, environment setup.

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


@pytest.fixture
def sample_article():
    return {
        "title": "Bitcoin hits $100K for the first time",
        "url": "https://cointelegraph.com/news/bitcoin-100k",
        "content": "Bitcoin surpassed $100,000 for the first time today as institutional demand continued to grow. The milestone was reached after months of steady accumulation by ETF funds.",
        "published_at": datetime(2026, 6, 17, 10, 0, 0),
        "source_name": "CoinTelegraph"
    }


@pytest.fixture
def sample_blockworks_article():
    return {
        "title": "ETH derivatives reset signals next move",
        "url": "https://blockworks.co/news/eth-derivatives-reset",
        "content": "Ethereum's derivatives market has fully reset after a period of overleveraged longs. Open interest has dropped 40% signaling the market is ready for the next directional move.",
        "published_at": datetime(2026, 6, 17, 12, 0, 0),
        "source_name": "Blockworks"
    }


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.articles = MagicMock()
    db.articles.find_one = AsyncMock(return_value=None)
    db.articles.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
    db.articles.update_one = AsyncMock(return_value=None)
    db.keywords = MagicMock()
    db.keywords.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"word": "bitcoin", "category_name": "Bitcoin"},
            {"word": "btc", "category_name": "Bitcoin"},
            {"word": "ethereum", "category_name": "Ethereum"},
            {"word": "eth", "category_name": "Ethereum"},
        ])
    ))
    return db
```

WHY conftest.py (not inline fixtures):
- Fixtures defined in conftest.py are automatically available to all test files
- Sample articles defined once — if the article schema changes, update one place
- Mock DB setup defined once — all tests share the same mock behavior

---

### tests/test_scraper.py

PURPOSE: Verify both scrapers return correctly-shaped article dicts without hitting live sites.

```python
import pytest
from unittest.mock import patch, AsyncMock
from scrapers.cointelegraph import CoinTelegraphScraper
from scrapers.blockworks import BlockworksScraper

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Bitcoin hits $100K</title>
      <link>https://cointelegraph.com/news/bitcoin-100k</link>
      <pubDate>Tue, 17 Jun 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

SAMPLE_ARTICLE_HTML = """<html><body>
  <article>
    <p>Bitcoin surpassed $100,000 for the first time today as institutional demand grew.</p>
    <p>The milestone was reached after months of steady accumulation by ETF funds globally.</p>
    <p>Analysts expect this level to become strong support going forward.</p>
  </article>
</body></html>"""

BLOCKWORKS_API_RESPONSE = [
    {
        "title": "ETH derivatives reset",
        "slug": "eth-derivatives-reset",
        "content": "<p>Ethereum's derivatives market has fully reset. Open interest dropped 40%.</p>",
        "publishedAt": "Tue, 17 Jun 2026 12:00:00 GMT"
    }
]


@pytest.mark.asyncio
async def test_cointelegraph_returns_articles():
    scraper = CoinTelegraphScraper()
    with patch.object(scraper, "fetch_page", side_effect=[
        AsyncMock(return_value=SAMPLE_RSS)(),
        AsyncMock(return_value=SAMPLE_ARTICLE_HTML)()
    ]):
        results = await scraper.scrape()
    assert len(results) == 1
    assert results[0]["title"] == "Bitcoin hits $100K"
    assert results[0]["source_name"] == "CoinTelegraph"
    assert len(results[0]["content"]) >= 50


@pytest.mark.asyncio
async def test_cointelegraph_article_has_required_keys(sample_article):
    required_keys = {"title", "url", "content", "published_at", "source_name"}
    assert required_keys.issubset(sample_article.keys())


@pytest.mark.asyncio
async def test_blockworks_returns_articles():
    scraper = BlockworksScraper()
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = BLOCKWORKS_API_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        results = await scraper.scrape()
    assert len(results) == 1
    assert results[0]["source_name"] == "Blockworks"
    assert "content" in results[0]


def test_blockworks_parse_date_iso():
    scraper = BlockworksScraper()
    from datetime import datetime
    result = scraper._parse_date("2026-06-17T10:00:00Z")
    assert isinstance(result, datetime)
    assert result.year == 2026


def test_blockworks_parse_date_rfc2822():
    scraper = BlockworksScraper()
    from datetime import datetime
    result = scraper._parse_date("Tue, 17 Jun 2026 10:00:00 GMT")
    assert isinstance(result, datetime)
    assert result.month == 6


def test_blockworks_parse_date_fallback():
    scraper = BlockworksScraper()
    from datetime import datetime
    result = scraper._parse_date(None)
    assert isinstance(result, datetime)
```

---

### tests/test_cleaner.py

PURPOSE: Verify all cleaning rules produce the correct output.

```python
from utils.cleaner import clean_html, normalize_url, normalize_timestamp, clean_article
from datetime import datetime


def test_clean_html_strips_tags():
    assert clean_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_clean_html_collapses_whitespace():
    assert clean_html("<p>  too   many   spaces  </p>") == "too many spaces"


def test_clean_html_handles_empty():
    assert clean_html("") == ""
    assert clean_html(None) == ""


def test_normalize_url_strips_query_params():
    url = "https://cointelegraph.com/news/bitcoin-100k?ref=twitter&utm_source=rss"
    assert normalize_url(url) == "https://cointelegraph.com/news/bitcoin-100k"


def test_normalize_url_lowercases():
    assert normalize_url("https://CoinTelegraph.com/News/BTC") == "https://cointelegraph.com/news/btc"


def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://cointelegraph.com/news/bitcoin/") == "https://cointelegraph.com/news/bitcoin"


def test_normalize_timestamp_passes_through_datetime():
    dt = datetime(2026, 6, 17, 10, 0, 0)
    result = normalize_timestamp(dt)
    assert isinstance(result, datetime)
    assert result.year == 2026


def test_clean_article_applies_all_cleaners():
    raw = {
        "title": "  Bitcoin ETF  ",
        "url": "https://example.com/news?ref=rss",
        "content": "<p>Bitcoin hit <b>$100K</b></p>",
        "published_at": datetime(2026, 6, 17),
        "source_name": "CoinTelegraph"
    }
    cleaned = clean_article(raw)
    assert cleaned["title"] == "Bitcoin ETF"
    assert "ref=rss" not in cleaned["url"]
    assert "<p>" not in cleaned["content"]
    assert "<b>" not in cleaned["content"]
```

---

### tests/test_classifier.py

PURPOSE: Verify keyword matching returns the correct category.

```python
import pytest
from services.classifier import classify_article, load_keywords


@pytest.mark.asyncio
async def test_classify_bitcoin_article(mock_db):
    await load_keywords(mock_db)
    category = classify_article(
        title="Bitcoin hits $100K for first time",
        content="The price of bitcoin surged past one hundred thousand dollars."
    )
    assert category == "Bitcoin"


@pytest.mark.asyncio
async def test_classify_ethereum_article(mock_db):
    await load_keywords(mock_db)
    category = classify_article(
        title="Ethereum upgrade approved",
        content="The Ethereum network will undergo a major protocol upgrade next month."
    )
    assert category == "Ethereum"


@pytest.mark.asyncio
async def test_classify_title_weighted_higher(mock_db):
    await load_keywords(mock_db)
    # Title says Bitcoin, body mentions Ethereum once
    category = classify_article(
        title="Bitcoin dominance grows",
        content="While ethereum has also performed well, bitcoin continues to lead the market cap rankings."
    )
    assert category == "Bitcoin"


@pytest.mark.asyncio
async def test_classify_uncategorized_when_no_match(mock_db):
    await load_keywords(mock_db)
    category = classify_article(
        title="Stock markets surge",
        content="The S&P 500 hit a record high today as tech stocks rallied."
    )
    assert category == "Uncategorized"


@pytest.mark.asyncio
async def test_classify_empty_cache_returns_uncategorized():
    # Don't load keywords — cache is empty
    from services import classifier
    classifier._keyword_map = {}
    category = classify_article("Bitcoin news", "Bitcoin price analysis")
    assert category == "Uncategorized"
```

---

### tests/test_dedup.py

PURPOSE: Verify the duplicate detection guard works at both the pre-check and DB index levels.

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from database import crud


@pytest.mark.asyncio
async def test_article_exists_returns_true_when_found():
    db = MagicMock()
    db.articles.find_one = AsyncMock(return_value={"_id": "abc123"})
    result = await crud.article_exists(db, "https://example.com/news/bitcoin")
    assert result is True


@pytest.mark.asyncio
async def test_article_exists_returns_false_when_not_found():
    db = MagicMock()
    db.articles.find_one = AsyncMock(return_value=None)
    result = await crud.article_exists(db, "https://example.com/news/new-article")
    assert result is False


@pytest.mark.asyncio
async def test_insert_article_returns_none_on_duplicate():
    from pymongo.errors import DuplicateKeyError
    db = MagicMock()
    db.articles.insert_one = AsyncMock(side_effect=DuplicateKeyError(""))
    result = await crud.insert_article(db, {"url": "https://example.com/already-exists"})
    assert result is None


@pytest.mark.asyncio
async def test_insert_article_returns_id_on_success():
    db = MagicMock()
    db.articles.insert_one = AsyncMock(return_value=MagicMock(inserted_id="newid123"))
    result = await crud.insert_article(db, {"url": "https://example.com/new"})
    assert result == "newid123"
```

---

### tests/test_telegram.py

PURPOSE: Verify message formatting and API call behavior without sending real Telegrams.

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.telegram_poster import format_message, send_message, _escape_html


def test_escape_html_escapes_ampersand():
    assert _escape_html("BTC & ETH") == "BTC &amp; ETH"


def test_escape_html_escapes_angle_brackets():
    assert _escape_html("price > $100K") == "price &gt; $100K"
    assert _escape_html("<strong>news</strong>") == "&lt;strong&gt;news&lt;/strong&gt;"


def test_format_message_contains_title():
    msg = format_message(
        title="Bitcoin hits $100K",
        content="Bitcoin surpassed $100,000 today.",
        url="https://cointelegraph.com/news/bitcoin-100k",
        source_name="CoinTelegraph",
        category="Bitcoin"
    )
    assert "Bitcoin hits $100K" in msg
    assert "CoinTelegraph" in msg
    assert "Bitcoin" in msg
    assert "https://cointelegraph.com/news/bitcoin-100k" in msg


def test_format_message_escapes_special_chars():
    msg = format_message(
        title="BTC & ETH rise",
        content="Markets surging.",
        url="https://example.com",
        source_name="Test",
        category="Bitcoin"
    )
    assert "&amp;" in msg
    assert "BTC & ETH" not in msg


@pytest.mark.asyncio
async def test_send_message_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 42}}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await send_message("Test message")

    assert result["message_id"] == 42


@pytest.mark.asyncio
async def test_send_message_retries_on_rate_limit():
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 1"
            }
            return mock_response
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 99}}
        return mock_response

    with patch("httpx.AsyncClient") as mock_client:
        with patch("asyncio.sleep", AsyncMock()):
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await send_message("Test message")

    assert call_count == 2
    assert result["message_id"] == 99
```

---

### tests/test_ai_rewriter.py

PURPOSE: Verify AI rewrite calls the correct endpoint and falls back gracefully on failure.

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.ai_rewriter import rewrite_article, _truncate_fallback


def test_truncate_fallback_cuts_at_sentence():
    long_content = "First sentence is here. Second sentence continues. Third sentence is the longest one of all the sentences in this test."
    result = _truncate_fallback(long_content, max_chars=60)
    assert result.endswith(".")
    assert len(result) <= 60


def test_truncate_fallback_returns_as_is_when_short():
    short = "Short content."
    assert _truncate_fallback(short) == short


@pytest.mark.asyncio
async def test_rewrite_article_calls_gemini():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Rewritten crypto news summary."}]}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        with patch("services.ai_rewriter.AI_API_KEY", "test-key"):
            result = await rewrite_article("Bitcoin news", "Long article content here.")

    assert result == "Rewritten crypto news summary."


@pytest.mark.asyncio
async def test_rewrite_article_uses_fallback_on_api_failure():
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("Network error")
        )
        with patch("services.ai_rewriter.AI_API_KEY", "test-key"):
            result = await rewrite_article("Bitcoin news", "Some content that is short enough.")

    assert "Some content" in result


@pytest.mark.asyncio
async def test_rewrite_article_uses_fallback_when_no_api_key():
    with patch("services.ai_rewriter.AI_API_KEY", None):
        result = await rewrite_article("Bitcoin news", "Content for the article.")

    assert len(result) > 0
```

---

### New dependencies for Day 4 tests

```
pytest
pytest-asyncio
pytest-mock
```

Add to requirements.txt and install:

```
pip install pytest pytest-asyncio pytest-mock
```

Add to root directory: `pytest.ini`

```ini
[pytest]
asyncio_mode = auto
```

WHY asyncio_mode = auto:
- Without it, every async test needs @pytest.mark.asyncio decorator
- With auto mode, all async test functions are treated as async automatically
- Less boilerplate, no forgotten decorator causing a test to silently not run

---

## PHASE 2 — ERROR HANDLING HARDENING (~1.5 hrs)

### Current state of error handling (what exists)

| Location | What exists | Gap |
|---|---|---|
| crud.insert_article | DuplicateKeyError caught | Good — no gap |
| scraper_service.py | return_exceptions=True on gather | Good — one scraper failure doesn't kill the other |
| dispatcher.py | try/except per article with continue | Good — one bad article doesn't kill dispatch |
| ai_rewriter.py | Fallback to truncation | Good — no gap |
| send_message() | Retry on 429 with retry_after delay | Good — no gap |
| Scheduler tick | No top-level exception handling | GAP |
| MongoDB connection | No reconnect logic | GAP |
| Article with empty content | Not explicitly guarded | GAP |

### Fix 1 — Scheduler tick top-level guard

Add to scheduler/scheduler.py:

```python
async def scheduled_run():
    try:
        from database.db import get_db
        from services.scraper_service import run_scrapers
        from services.dispatcher import dispatch_articles
        db = get_db()
        logger.info("=== Scheduled run starting ===")
        scrape_result = await run_scrapers()
        dispatch_result = await dispatch_articles(db)
        logger.info(f"=== Scheduled run complete: scrape={scrape_result}, dispatch={dispatch_result} ===")
    except Exception as e:
        logger.error(f"=== Scheduled run FAILED: {e} ===", exc_info=True)
        # Do NOT re-raise — scheduler must continue to next tick even on failure
```

WHY not re-raise in the scheduler:
- If the scheduler function raises, APScheduler catches it but may pause or stop the job
- A transient failure (Atlas blip, Telegram timeout) should not stop future scheduled runs
- Log it visibly, continue to next tick

### Fix 2 — Content guard before AI rewrite

Add to dispatcher.py before calling rewrite_article:

```python
if not article.get("content") or len(article["content"]) < 50:
    logger.warning(f"Article '{article.get('title', '')[:50]}' has no usable content — skipping")
    failed += 1
    continue
```

WHY 50 chars minimum:
- The AI prompt is useless with less than a sentence of content
- The fallback truncation with < 50 chars produces a meaningless Telegram post
- Better to skip and investigate than post garbage to the channel

### Fix 3 — Telegram message length guard

Add to dispatcher.py before send_message:

```python
MAX_TELEGRAM_LENGTH = 4096

if len(message) > MAX_TELEGRAM_LENGTH:
    # Trim the rewritten content to fit, preserve header and footer
    overage = len(message) - MAX_TELEGRAM_LENGTH
    rewritten = rewritten[: len(rewritten) - overage - 10] + "..."
    message = format_message(title, rewritten, url, source_name, category)
```

WHY this happens:
- Telegram hard-limits messages to 4,096 characters
- The AI rewrite is prompted to stay under 800 chars but occasionally returns more
- Without this guard, send_message() returns a 400 Bad Request and the article is never posted

---

## PHASE 3 — HEALTH CHECK ENDPOINT (~30 mins)

### api/routers/health.py

PURPOSE: Single endpoint that confirms the app is alive, connected to MongoDB, and the scheduler is running.

WHY a health endpoint:
- Without it, you can't tell if the bot is running or crashed silently
- Any monitoring tool (uptime robot, cron ping, status page) can hit /health every minute
- Also useful during development: a quick GET tells you if the whole stack is connected

```python
from fastapi import APIRouter
from database.db import get_db
from scheduler.scheduler import scheduler

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    status = {"status": "ok", "mongodb": "unknown", "scheduler": "unknown"}

    try:
        db = get_db()
        await db.command("ping")
        status["mongodb"] = "connected"
    except Exception as e:
        status["mongodb"] = f"error: {str(e)}"
        status["status"] = "degraded"

    status["scheduler"] = "running" if scheduler.running else "stopped"
    if not scheduler.running:
        status["status"] = "degraded"

    return status
```

Expected healthy response:
```json
{ "status": "ok", "mongodb": "connected", "scheduler": "running" }
```

Mount in main.py:
```python
from api.routers.health import router as health_router
app.include_router(health_router)
```

---

## PHASE 4 — DEPLOYMENT (~1.5 hrs)

### Option A — Always-on on current Windows machine (simplest)

Run the FastAPI app as a background process that survives terminal close:

```powershell
# Install nssm (Non-Sucking Service Manager) to run as Windows service
# Or use pythonw to detach from terminal:

Start-Process pythonw -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "C:\Users\Aneeq\Desktop\TelegramBot" -WindowStyle Hidden
```

Or use a .bat file:

```bat
@echo off
cd C:\Users\Aneeq\Desktop\TelegramBot
start /B pythonw -m uvicorn main:app --host 0.0.0.0 --port 8000 > logs\uvicorn.log 2>&1
```

WHY pythonw over python:
- python.exe keeps a terminal window open
- pythonw.exe runs without a terminal window — true background process

---

### Option B — Linux VPS (recommended for always-on)

Deploy to any Ubuntu VPS (DigitalOcean $6/month, Hetzner $4/month, or Oracle Free Tier):

**Step 1 — Upload project**
```bash
scp -r C:\Users\Aneeq\Desktop\TelegramBot user@your-vps-ip:/home/user/TelegramBot
```

**Step 2 — Install dependencies**
```bash
cd /home/user/TelegramBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Step 3 — Create systemd service**

Create `/etc/systemd/system/telegrambot.service`:

```ini
[Unit]
Description=Telegram News Bot
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/TelegramBot
EnvironmentFile=/home/user/TelegramBot/.env
ExecStart=/home/user/TelegramBot/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Step 4 — Enable and start**
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegrambot
sudo systemctl start telegrambot
sudo systemctl status telegrambot
```

WHY systemd:
- Starts on boot automatically
- Restarts on crash (Restart=always + RestartSec=10)
- Logs to journald: `journalctl -u telegrambot -f`
- Standard Linux service management

---

### Pre-deployment checklist

Run through ALL of these before going live:

```
[ ] All tests pass: pytest tests/ -v
[ ] .env has all 7 required variables set (no empty values)
[ ] TELEGRAM_BOT_TOKEN works: curl https://api.telegram.org/bot{TOKEN}/getMe
[ ] TELEGRAM_CHANNEL_ID correct: bot is admin of the channel
[ ] AI_API_KEY valid: test rewrite_article() directly
[ ] MongoDB Atlas Network Access: VPS IP is whitelisted (or 0.0.0.0/0 for testing)
[ ] GET /health returns status: ok
[ ] POST /api/v1/admin/run-now posts one article to the channel
[ ] Check the Telegram channel: message format looks correct
[ ] Rerun pipeline: same article is NOT posted twice (is_posted guard confirmed)
[ ] Let scheduler run one full tick: new articles appear without manual trigger
```

---

## FINAL FOLDER STRUCTURE AFTER DAY 4

```
TelegramBot/
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py
│   ├── cointelegraph.py
│   └── blockworks.py
├── services/
│   ├── __init__.py
│   ├── scraper_service.py
│   ├── classifier.py
│   ├── ai_rewriter.py
│   ├── telegram_poster.py
│   └── dispatcher.py
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
│       ├── channels.py
│       ├── articles.py
│       ├── dashboard.py
│       ├── admin.py
│       └── health.py
├── scheduler/
│   ├── __init__.py
│   └── scheduler.py
├── utils/
│   ├── __init__.py
│   ├── config.py
│   ├── logger.py
│   └── cleaner.py
├── templates/
│   ├── base.html
│   ├── sources.html
│   ├── categories.html
│   ├── keywords.html
│   ├── channels.html
│   └── articles.html
├── static/
│   └── style.css
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_scraper.py
│   ├── test_cleaner.py
│   ├── test_classifier.py
│   ├── test_dedup.py
│   ├── test_telegram.py
│   └── test_ai_rewriter.py
├── plan/
│   ├── day1.md
│   ├── day2.md
│   ├── day3.md
│   └── day4.md
├── pytest.ini
├── .env
├── requirements.txt
├── run_scraper.py
└── main.py
```

---

## DAY 4 SUCCESS CRITERIA — PROJECT COMPLETE

Verify ALL of these before considering the project done:

1. pytest tests/ -v — ALL tests pass, zero failures
2. GET /health — returns { "status": "ok", "mongodb": "connected", "scheduler": "running" }
3. POST /api/v1/admin/run-now — logs show scrape + AI rewrite + Telegram post completing
4. Telegram channel shows new posts with correct format (title, summary, source link, category)
5. MongoDB articles collection: confirmed is_posted=True on posted articles
6. MongoDB logs collection: confirmed log entry exists with telegram_message_id for each post
7. Re-run pipeline 3 times — same articles never posted twice
8. Scheduler runs automatically — articles appear in channel without any manual action
9. Restart the app — scheduler resumes, next tick completes normally
10. GET /health after restart — all three indicators green

---

## COMMON ERRORS AND FIXES — DAY 4

| Error | Cause | Fix |
|-------|-------|-----|
| pytest: no tests ran | pytest.ini asyncio_mode missing | Add asyncio_mode = auto to pytest.ini |
| coroutine never awaited in test | Missing await on async mock | Wrap mock return value: AsyncMock(return_value=...) |
| ImportError in tests | Test imports fail because of DB at import time | Restructure to lazy imports or use conftest fixtures |
| systemd service fails to start | Wrong WorkingDirectory path | Confirm path with ls /home/user/TelegramBot |
| Bot posts work locally but not on VPS | Atlas IP not whitelisted | Add VPS IP to Atlas Network Access → Allow List |
| Messages truncated mid-word | Message length not checked before send | Add length guard in dispatcher before send_message() |
| All articles stay Uncategorized on VPS | load_keywords() not called on startup | Confirm lifespan in main.py calls await load_keywords(db) |
| Scheduler stops after first error | Exception re-raised in scheduled_run | Wrap scheduled_run body in try/except, log error, do not re-raise |
