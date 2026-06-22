# Telegram News Bot

An automated crypto-news pipeline that scrapes articles from crypto news sites, cleans and classifies them by keyword, optionally rewrites them with an AI model, and posts them to a Telegram channel on a fixed schedule. It ships with a **FastAPI** backend (REST API + background scheduler) and a **Next.js** admin frontend.

## How it works

Every `SCRAPE_INTERVAL_MINUTES` the scheduler runs the full pipeline:

```
scrapers  ->  cleaner  ->  classifier  ->  AI rewriter  ->  Telegram dispatcher
(httpx)       (normalize)   (keywords)      (optional)       (Bot API)
```

1. **Scrapers** fetch the latest articles from each source (CoinTelegraph, Blockworks). They use `httpx` with a browser User-Agent and fall back gracefully when Cloudflare blocks a request.
2. **Cleaner** normalizes the raw article (title, content, url).
3. **Classifier** assigns a category by matching keywords loaded from MongoDB into an in-memory cache at startup.
4. **AI rewriter** can rewrite the article text using a configurable model (optional).
5. **Dispatcher** formats the article and posts it to the configured Telegram channel via the raw Telegram Bot API (HTML parse mode, with automatic retry on rate limits).

State (sources, categories, keywords, channels, articles) lives in **MongoDB** and is managed through the REST API.

## Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Uvicorn |
| Scheduler | APScheduler (AsyncIOScheduler) |
| Database | MongoDB (Motor async driver) |
| HTTP | httpx |
| Frontend | Next.js (App Router) + TypeScript |
| Config | python-dotenv |

## Project structure

```
.
├── main.py              # FastAPI entry point (lifespan: DB -> keywords -> scheduler)
├── run_scraper.py       # Run a single scraper manually from the CLI
├── api/
│   └── routers/         # REST endpoints (sources, categories, keywords, channels, articles, admin, health)
├── database/
│   └── db.py            # MongoDB (Motor) connection manager
├── scrapers/
│   ├── base_scraper.py  # Shared httpx fetch + Cloudflare handling
│   ├── cointelegraph.py
│   └── blockworks.py
├── services/
│   ├── scraper_service.py  # Runs all scrapers
│   ├── classifier.py       # Keyword-based categorization
│   ├── ai_rewriter.py      # Optional AI rewrite
│   ├── dispatcher.py       # Orchestrates posting unsent articles
│   └── telegram_poster.py  # Telegram Bot API client
├── scheduler/
│   └── scheduler.py     # Interval job: scrape + dispatch
├── utils/               # config, logger, cleaner helpers
└── frontend/            # Next.js admin UI
```

## Getting started (backend)

### Prerequisites

- Python 3.10+
- A MongoDB database (e.g. MongoDB Atlas)
- A Telegram bot token and a channel the bot can post to

### Install

```bash
git clone https://github.com/aneeqbutt/Telegram_bot
cd Telegram_bot

python -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

If `requirements.txt` is not present yet, install the core dependencies directly:

```bash
pip install "fastapi" "uvicorn[standard]" motor certifi apscheduler httpx python-dotenv
```

### Configure

Create a `.env` file in the project root:

```env
# MongoDB
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net
DB_NAME=telegrambot

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token
TELEGRAM_CHANNEL_ID=@your_channel_or_-100xxxxxxxxxx

# AI rewriter (optional)
AI_API_KEY=your-api-key
AI_MODEL=nex-agi/nex-n2-pro:free

# Pipeline
SCRAPE_INTERVAL_MINUTES=60
MAX_RETRY_COUNT=3
LOG_LEVEL=INFO
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGODB_URI` | yes | – | MongoDB connection string |
| `DB_NAME` | no | `telegrambot` | Database name |
| `TELEGRAM_BOT_TOKEN` | yes | – | Telegram bot token from @BotFather |
| `TELEGRAM_CHANNEL_ID` | yes | – | Target channel (`@handle` or numeric `-100...` id) |
| `AI_API_KEY` | no | – | API key for the AI rewriter |
| `AI_MODEL` | no | `nex-agi/nex-n2-pro:free` | Model used for rewriting |
| `SCRAPE_INTERVAL_MINUTES` | no | `60` | How often the pipeline runs |
| `MAX_RETRY_COUNT` | no | `3` | Max retries for outbound requests |
| `LOG_LEVEL` | no | `INFO` | Logging level |

### Run

```bash
uvicorn main:app --reload
```

On startup the app connects to MongoDB, loads keywords into the classifier cache, and starts the scheduler. The API is then available at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`).

### Run a scraper manually

You can run a single scraper from the CLI without waiting for the scheduler:

```bash
python run_scraper.py cointelegraph
python run_scraper.py blockworks
```

This scrapes a few articles, classifies them, and prints the result (it does not post to Telegram).

## API

All resource routes are mounted under `/api/v1`:

| Resource | Path |
|---|---|
| Sources | `/api/v1/sources` |
| Categories | `/api/v1/categories` |
| Keywords | `/api/v1/keywords` |
| Channels | `/api/v1/channels` |
| Articles | `/api/v1/articles` |
| Admin | `/api/v1/admin` |
| Health | `/health` |

See the auto-generated Swagger UI at `/docs` for full request/response schemas.

## Getting started (frontend)

The admin UI is a Next.js app in `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

It runs on `http://localhost:3000`, which is the origin allowed by the backend's CORS configuration.

## License

No license file is currently included in the repository. If you intend others to reuse this project, consider adding one (for example, MIT).
