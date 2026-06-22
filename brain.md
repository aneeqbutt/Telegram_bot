# Telegram News Bot — Project Brain
# Full context from Claude sessions + Gemini IDE session

---

## PROJECT OVERVIEW

**Goal:** Fully automated Telegram crypto news bot.
Scrapes CoinTelegraph and Blockworks → classifies by keyword → rewrites with Gemini AI → posts to Telegram channel → repeats on a schedule. Admin dashboard to manage sources, categories, keywords, channels, and view articles.

**Stack:** Python 3.12.10 + FastAPI (async) + MongoDB Atlas + Next.js 14 (admin dashboard)
**Database:** MongoDB Atlas M0 free tier, cluster: `cluster0.wruxzmt.mongodb.net`, DB: `telegrambot`
**Working directory:** `C:\Users\Aneeq\Desktop\TelegramBot`

---

## CURRENT STATE (as of Jun 17, 2026)

### Completed
- Day 1: Scrapers, MongoDB Atlas, 3-layer Cloudflare bypass, deduplication
- Day 2: Cleaner, classifier, FastAPI CRUD API (all routers), extended crud.py and models.py (done in Gemini IDE session)
- Blockworks rewritten to use `/api/posts` JSON endpoint (zero Cloudflare friction)
- Next.js admin dashboard: all 6 pages built + all UI components written, dev server running at `http://localhost:3000`

### Pending
- Day 3: AI rewriter, Telegram poster, dispatcher, APScheduler
- Day 4: Test suite, error hardening, health check endpoint, deployment
- Update goals file: Day 2 now complete

---

## TECH STACK PER LAYER

| Layer | Tech |
|---|---|
| Backend framework | FastAPI (async) with lifespan context manager |
| Database driver | Motor 3.6.0 (async) + pymongo 4.9.2 (sync, for init_db.py) |
| Database | MongoDB Atlas M0 free tier |
| SSL (Windows) | certifi (required for Atlas connection on Windows) |
| DNS | dnspython (required for `mongodb+srv://` resolution) |
| HTTP client | httpx (async, used everywhere) |
| HTML parsing | BeautifulSoup4 |
| Cloudflare bypass L1 | httpx — fast, async |
| Cloudflare bypass L2 | cloudscraper — TLS fingerprint spoof |
| Cloudflare bypass L3 | SeleniumBase UC Mode — Chrome binary patch |
| Scheduler | APScheduler AsyncIOScheduler |
| AI rewriting | Google Gemini Flash free API (1,500 req/day free) |
| Telegram posting | Raw httpx POST to Bot API (no python-telegram-bot) |
| Admin frontend | Next.js 14 App Router + TypeScript + Tailwind CSS |
| UI components | Radix UI primitives (manually written, NOT shadcn CLI) |
| Data fetching | TanStack Query (React Query) |
| Notifications | sonner (Toaster) |
| Form utilities | clsx + tailwind-merge (cn()), class-variance-authority (CVA) |

---

## FOLDER STRUCTURE (full, after Day 4)

```
TelegramBot/
├── scrapers/
│   ├── base_scraper.py     — 3-layer CF bypass system (abstract base)
│   ├── cointelegraph.py    — RSS feed → httpx → full article page
│   └── blockworks.py       — Direct /api/posts JSON endpoint (no CF)
├── services/
│   ├── scraper_service.py  — Orchestrates both scrapers
│   ├── classifier.py       — Keyword matching, in-memory cache
│   ├── ai_rewriter.py      — Gemini Flash API + truncation fallback [Day 3]
│   ├── telegram_poster.py  — Format + send via Bot API + 429 retry [Day 3]
│   └── dispatcher.py       — Read unposted → rewrite → post → mark [Day 3]
├── database/
│   ├── db.py               — Motor client singleton, connect/disconnect/get_db
│   ├── models.py           — Pydantic models for all collections
│   ├── crud.py             — All async DB operations (one place for all queries)
│   └── init_db.py          — One-time index creation + seed data
├── api/routers/
│   ├── sources.py          — GET/POST/PUT/DELETE /api/v1/sources
│   ├── categories.py       — GET/POST/PUT/DELETE /api/v1/categories
│   ├── keywords.py         — GET/POST/DELETE /api/v1/keywords (reloads classifier)
│   ├── channels.py         — GET/POST/PUT/DELETE /api/v1/channels
│   ├── articles.py         — GET /api/v1/articles (read-only, paginated)
│   ├── admin.py            — POST /api/v1/admin/run-now [Day 3]
│   └── health.py           — GET /health [Day 4]
├── scheduler/
│   └── scheduler.py        — APScheduler AsyncIOScheduler [Day 3]
├── utils/
│   ├── config.py           — Central env var loader
│   ├── logger.py           — Structured logger with timestamps
│   └── cleaner.py          — clean_html, normalize_url, normalize_timestamp
├── frontend/               — Next.js 14 admin dashboard
│   ├── app/dashboard/      — 6 pages: overview, articles, sources, categories, keywords, channels
│   ├── components/ui/      — button, badge, input, label, card, skeleton, table, dialog, select, switch, sonner, separator
│   └── lib/
│       ├── api.ts          — All API functions + TypeScript interfaces
│       ├── providers.tsx   — QueryClientProvider + Toaster
│       └── utils.ts        — cn() utility
├── tests/                  — [Day 4]
├── plan/
│   ├── day1.md, day2.md, day3.md, day4.md
├── daily-reports/
├── daily-standups/
├── goals/
├── .env
├── requirements.txt
├── run_scraper.py
└── main.py
```

---

## MONGODB SCHEMA

**Collections:** articles, sources, categories, keywords, channels, logs

**Key indexes:**
- `articles.url` — UNIQUE (deduplication mechanism)
- `articles.is_posted` — index (dispatch query runs against this every hour)
- `articles.published_at` — index
- `sources.base_url` — UNIQUE
- `channels.telegram_id` — UNIQUE
- `categories.name` — UNIQUE

**Article document shape:**
```
url, title, content, source_id, published_at, scraped_at, is_posted, category, rephrased_content
```

**Why UNIQUE index instead of pre-check:**
Two DB round-trips vs one. Race-condition safe against concurrent scrapers. DuplicateKeyError caught in `crud.insert_article()`, logged, returns None — never raises to caller.

---

## SCRAPER ARCHITECTURE

### CoinTelegraph
- Fetches RSS feed at `https://cointelegraph.com/rss`
- Parses all items (30 per feed), gets article URL from `<link>`
- Fetches each article page via httpx (Layer 1)
- Extracts content via BeautifulSoup from `<article>` tag
- 300-char minimum guard: discards content below threshold

### Blockworks (REWRITTEN Jun 17)
- **Old approach:** RSS feed → 3-layer CF bypass (all failed against Bot Management)
- **New approach:** Direct GET to `https://blockworks.com/api/posts?limit=50`
- Returns full JSON with HTML article content (5,565–19,187 chars per article)
- Zero Cloudflare protection on this endpoint
- Dual date parser: ISO 8601 first, then RFC 2822 (`GMT` → `+0000` for strptime)
- Why it works: internal React frontend API, not a public-facing page

### 3-Layer Cloudflare Bypass (base_scraper.py)
```
fetch_page(url)
  ├─ Layer 1: httpx — async, fast, < 1s. Works for RSS + unprotected pages.
  │           ↓ (if 403/503/429/520-524)
  ├─ Layer 2: cloudscraper — spoofs Chrome TLS, runs in executor (sync). Fails on Bot Mgmt.
  │           ↓ (if fails)
  └─ Layer 3: SeleniumBase UC Mode — patches Chrome binary, uc=True, runs in executor.
```

**Why cloudscraper/SeleniumBase run in executor:**
FastAPI runs on asyncio — one event loop. Blocking sync code in the loop freezes the entire app. `run_in_executor()` moves sync calls to worker threads.

**Known limitation:**
Cloudflare Bot Management (paid enterprise tier) operates at TLS/IP reputation level. No headless tool defeats it from a flagged IP. Blockworks uses this tier. Solution: use their API endpoint instead.

**SeleniumBase Turnstile flaws (diagnosed, now bypassed by API switch):**
1. `headless=True` leaks bot signals (empty plugins, SwiftShader WebGL, zero screen dims)
2. `uc_gui_click_captcha()` targets reCAPTCHA v2 image grids — wrong for Turnstile
3. 3s sleep insufficient — Turnstile fingerprinting takes 8-15s on suspicious sessions
4. Fresh Chrome instance per article = zero CF trust score (no cookie persistence)

---

## CLASSIFICATION SYSTEM (services/classifier.py)

- Keyword → category mapping loaded from MongoDB `keywords` collection on startup
- Stored in-memory `_keyword_map: dict[str, str]`
- `classify_article(title, content)`: title matched at 2x weight (concatenated twice before content)
- `load_keywords(db)` called in FastAPI lifespan before scheduler starts
- `reload_keywords(db)` called in keywords router after any POST/DELETE — cache refreshes immediately without server restart
- Returns "Uncategorized" if no keyword matches or cache is empty

**Why in-memory cache:**
20 articles × 60min runs = 480 unnecessary DB queries/day without cache. Cache once, reload only on admin keyword change.

---

## FASTAPI ENDPOINTS (all under /api/v1/)

| Endpoint | Method | Purpose |
|---|---|---|
| /sources | GET, POST | List and create sources |
| /sources/{id} | PUT, DELETE | Update and delete source |
| /categories | GET, POST | List and create categories |
| /categories/{id} | PUT, DELETE | Update and delete category |
| /keywords | GET, POST | List and create keywords (reloads classifier) |
| /keywords/{id} | DELETE | Delete keyword (reloads classifier) |
| /channels | GET, POST | List and create channels |
| /channels/{id} | PUT, DELETE | Update and delete channel |
| /articles | GET | Paginated article list (skip, limit, category, is_posted filters) |
| /articles/{id} | GET | Single article (read-only — articles owned by pipeline) |
| /admin/run-now | POST | Trigger full scrape + dispatch cycle in background [Day 3] |
| /health | GET | MongoDB + scheduler status [Day 4] |

**API design rules:**
- Routers call crud.py only — no raw Motor queries in routers
- All use `Depends(get_db)` for the Motor db handle
- Articles are read-only via API (writes bypass cleaning and classification)
- CORS enabled for `http://localhost:3000` (Next.js dashboard)

---

## NEXT.JS ADMIN DASHBOARD

**Port:** 3000 (FastAPI on 8000)
**Framework:** Next.js 14 App Router, TypeScript, Tailwind CSS

### Pages
| Page | Route | Features |
|---|---|---|
| Overview | /dashboard | Stat cards, category bar chart, system status, recent articles, "Run Now" button |
| Articles | /dashboard/articles | Paginated table (20/page), search, filter by category + status |
| Sources | /dashboard/sources | Table, active toggle (Switch), add modal, delete |
| Categories | /dashboard/categories | Table, active toggle, add modal, delete |
| Keywords | /dashboard/keywords | Table with color badges, filter by category, add modal with Select, delete |
| Channels | /dashboard/channels | Table with post interval, active toggle, add modal, delete |

### UI Components (all in frontend/components/ui/)
All written manually using standard Radix UI APIs — NOT via shadcn CLI.

| Component | Library |
|---|---|
| button.tsx | @radix-ui/react-slot + CVA |
| badge.tsx | CVA (no Radix) |
| input.tsx | Plain HTML input |
| label.tsx | @radix-ui/react-label |
| card.tsx | Plain HTML divs |
| skeleton.tsx | Plain HTML div (animate-pulse) |
| table.tsx | Plain HTML table elements |
| dialog.tsx | @radix-ui/react-dialog |
| select.tsx | @radix-ui/react-select |
| switch.tsx | @radix-ui/react-switch |
| sonner.tsx | sonner (Toaster wrapper) |
| separator.tsx | @radix-ui/react-separator |

**Why NOT shadcn CLI:**
shadcn 4.11 defaulted to `"style": "base-nova"` which uses `@base-ui/react` instead of Radix UI.
Base-ui API differences broke the components:
- `asChild` prop doesn't exist on base-ui's DialogTrigger
- `onValueChange` typed as `(value: string | null)` not `string`
- Missing `@base-ui/react` and `class-variance-authority` packages

**Fix:** Deleted components.json, installed Radix UI primitives directly, wrote components manually.

### Data Fetching
- TanStack Query for all server state
- All API functions in `frontend/lib/api.ts`
- Base URL: `http://localhost:8000/api/v1`
- TypeScript interfaces: Article, Source, Category, Keyword, Channel

---

## DAY 2 — GEMINI IDE SESSION CONTEXT

Day 2 (cleaner, classifier, FastAPI CRUD, crud.py extension, models.py extension) was implemented in a separate Gemini IDE session. Claude did not directly see this code being written but confirmed its presence via file system inspection.

**What Gemini built:**
- `utils/cleaner.py` — clean_html(), normalize_url(), normalize_timestamp(), clean_article()
- `services/classifier.py` — load_keywords(), reload_keywords(), classify_article() with title 2x weighting
- `database/crud.py` — Extended with 14+ functions covering all collections
- `database/models.py` — Extended with SourceCreate/Update, CategoryCreate/Update, KeywordCreate, ChannelCreate/Update
- `api/routers/sources.py`, `categories.py`, `keywords.py`, `channels.py`, `articles.py` — Full CRUD routers
- `services/scraper_service.py` — Modified to import and call classify_article() after cleaning

**What Gemini did NOT build (still pending):**
- admin.py router (Day 3)
- services/ai_rewriter.py (Day 3)
- services/telegram_poster.py (Day 3)
- services/dispatcher.py (Day 3)
- scheduler/scheduler.py (Day 3)
- All test files (Day 4)
- api/routers/health.py (Day 4)

**Key integration point:**
`main.py` wires everything together:
```python
from fastapi.middleware.cors import CORSMiddleware
from services.classifier import load_keywords
from api.routers import sources, categories, keywords, channels, articles

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    db = get_db()
    await load_keywords(db)   # Must run before scheduler
    yield
    await disconnect_db()
```

---

## ENVIRONMENT VARIABLES

```
MONGO_URI              — mongodb+srv://...@cluster0.wruxzmt.mongodb.net/telegrambot...
DB_NAME                — telegrambot
LOG_LEVEL              — INFO (DEBUG during active development)
TELEGRAM_BOT_TOKEN     — from @BotFather [needed Day 3]
TELEGRAM_CHANNEL_ID    — @channelname or -100xxxxxxxxxx [needed Day 3]
AI_API_KEY             — Gemini API key from aistudio.google.com [needed Day 3]
SCRAPE_INTERVAL_MINUTES — 60
MAX_RETRY_COUNT        — 3
```

---

## KEY ERRORS AND FIXES (from both sessions)

| Error | Root Cause | Fix |
|---|---|---|
| Blockworks 140 chars content | CF Bot Management at TLS/IP level — no bypass possible | Switch to `blockworks.com/api/posts` JSON API |
| RFC 2822 date parse failure | `fromisoformat()` can't parse `Wed, 07 Jan 2026 14:00:00 GMT` | Two-stage: ISO 8601 first, then RFC 2822 with `GMT→+0000` |
| Delete articles matched nothing | Queried by `source_name` field that doesn't exist in stored docs (stored as `source_id`) | Look up source `_id` from sources collection, then delete by `source_id` |
| shadcn Dialog `asChild` error | shadcn 4.11 uses base-nova style → `@base-ui/react` which has different API | Delete components.json, write Radix UI components manually |
| shadcn Select `onValueChange` type error | Base-ui Select types `onValueChange` as `(value: string \| null)` not `string` | Same fix — switch to `@radix-ui/react-select` |
| Cloudflare networkidle timeout | CF challenge page fires continuous background XHR → networkidle never triggers | Change `wait_until` to `"load"` with 60s timeout (Playwright experiment, now reverted) |
| `lib/utils.ts` missing | shadcn components.json pointed to `@/lib/utils` but file didn't exist | Create with `cn()` using clsx + tailwind-merge |
| `ServerSelectionTimeoutError` | IP not whitelisted in Atlas Network Access | Whitelist IP in Atlas → Network Access |
| Motor coroutine never awaited | Forgot `await` on Motor call | All Motor calls are async — always await them |
| Multiple lockfile warning in Next.js | Root `package-lock.json` + `frontend/package-lock.json` both detected | Harmless — no fix needed |

---

## DAY 3 PLAN SUMMARY (plan/day3.md)

**Phase 1 — AI Rewriter (services/ai_rewriter.py)**
- Calls `gemini-2.0-flash` via httpx POST to Gemini REST API
- Prompt: 3-5 sentence Telegram summary, no markdown, max 800 chars, end with "why this matters"
- Fallback: truncate content at last full sentence within 800 chars if API fails
- Content sliced to `content[:6000]` before sending (long articles, stays under token limit)

**Phase 2 — Telegram Poster (services/telegram_poster.py)**
- Raw httpx POST to `https://api.telegram.org/bot{TOKEN}/sendMessage`
- HTML parse_mode (not MarkdownV2 — crypto titles have too many special chars to escape)
- Message format: emoji title + rewritten content + link + source/category footer
- 429 retry: reads `retry_after` from API response description, sleeps exact duration

**Phase 3 — Dispatcher (services/dispatcher.py)**
- Reads all `is_posted=False` articles where `category != "Uncategorized"`
- For each: rewrite → format → send → mark posted → log to `logs` collection
- `sleep(1)` between posts (Telegram 1 msg/sec channel limit)
- `continue` on failure (one bad article doesn't kill the queue)

**Phase 4 — APScheduler (scheduler/scheduler.py)**
- `AsyncIOScheduler` (not BackgroundScheduler — must be async for Motor/httpx)
- Reads `SCRAPE_INTERVAL_MINUTES` from config
- Imports inside `scheduled_run()` to avoid circular imports
- Started in `lifespan` AFTER `load_keywords(db)` is complete

**Phase 5 — Admin Trigger (api/routers/admin.py)**
- `POST /api/v1/admin/run-now` — returns 200 immediately
- Uses FastAPI `BackgroundTasks` to run pipeline async without blocking the HTTP connection

---

## DAY 4 PLAN SUMMARY (plan/day4.md)

**Phase 1 — Test Suite (7 files)**
- `tests/conftest.py` — shared fixtures: sample_article, mock_db
- `tests/test_scraper.py` — mock HTTP, assert article dict shape
- `tests/test_cleaner.py` — assert HTML stripped, URL normalized, timestamps parsed
- `tests/test_classifier.py` — keyword matching, title weighting, empty cache
- `tests/test_dedup.py` — DuplicateKeyError path, article_exists()
- `tests/test_telegram.py` — format_message(), HTML escaping, 429 retry
- `tests/test_ai_rewriter.py` — Gemini call, truncation fallback, no-key fallback

**Phase 2 — Error Hardening (3 fixes)**
1. Scheduler tick: wrap `scheduled_run()` body in `try/except`, log error, do NOT re-raise
2. Content guard: skip articles with < 50 chars content before AI call
3. Telegram length guard: trim rewritten content if message > 4096 chars before send

**Phase 3 — Health Check (api/routers/health.py)**
```
GET /health → { "status": "ok", "mongodb": "connected", "scheduler": "running" }
```

**Phase 4 — Deployment**
- Windows: `pythonw -m uvicorn main:app` (no terminal window)
- Linux VPS: systemd service with `Restart=always` + `RestartSec=10`

---

## IMPORTANT PATTERNS AND DECISIONS

**Why FastAPI lifespan over @app.on_event:**
`on_event` is deprecated in newer FastAPI. Lifespan is the current pattern.

**Why Motor single client (not per-request):**
Motor clients are expensive to create. Connection pooling happens inside Motor.

**Why articles are read-only via API:**
Writes would bypass cleaning and classification — two separate code paths for article data is a maintenance trap.

**Why /api/v1/ prefix from day one:**
Zero cost to add now. Adding later requires versioning all existing clients.

**Why BackgroundTasks for admin/run-now:**
Scrape + dispatch takes 30-120 seconds. Direct await leaves HTTP connection open the whole time.

**Why AsyncIOScheduler (not BackgroundScheduler):**
BackgroundScheduler runs in a thread. Async Motor/httpx calls in a thread cause "coroutine never awaited" errors.

**Why HTML parse_mode for Telegram:**
MarkdownV2 requires escaping 18+ chars including `.`, `!`, `-`. Crypto titles have all of them.

**Why Gemini Flash (not Claude API for rewriting):**
1,500 req/day free with no credit card. Fast (~2-3s). Large enough context for 19K char articles.

**Why certifi for MongoDB on Windows:**
Windows doesn't ship with a CA bundle that Python can use for Atlas SSL. certifi provides one.

---

## RUNNING THE PROJECT

**Start FastAPI backend:**
```
cd C:\Users\Aneeq\Desktop\TelegramBot
uvicorn main:app --reload
```
API docs: http://localhost:8000/docs

**Start Next.js frontend:**
```
cd C:\Users\Aneeq\Desktop\TelegramBot\frontend
npm run dev
```
Dashboard: http://localhost:3000

**One-time setup:**
```
python database/init_db.py     # Create collections, indexes, seed data
```

**Manual scrape run:**
```
python run_scraper.py
```

**Run tests (Day 4):**
```
pytest tests/ -v
```
