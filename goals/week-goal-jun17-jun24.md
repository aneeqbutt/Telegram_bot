# Build "Telegram Crypto News Bot" (Jun 17 - Jun 24)

## Problem Statement

A working scraper layer exists that pulls articles from CoinTelegraph (full content via httpx) and Blockworks (RSS fallback due to Cloudflare Bot Management blocking article pages). However the pipeline stops at raw storage — there is no classification, no AI rewriting, no Telegram posting, and no scheduler running the cycle automatically. The bot as a product does not yet exist: it scrapes but never posts. The remaining three days of the implementation plan (Day 2: pipeline, Day 3: automation, Day 4: testing) need to be completed before the bot can operate end-to-end without manual intervention.

## Solution Approach

- Implement `utils/cleaner.py` to strip HTML, normalize whitespace, and remove boilerplate from stored article content
- Implement `services/classifier.py` with keyword matching against the seeded categories (Bitcoin, Ethereum, DeFi, Regulation, NFT) and update each article's category field in MongoDB after classification
- Investigate and implement DrissionPage as Layer 3 replacement to bypass Cloudflare Turnstile on Blockworks article pages and get full content instead of RSS summaries
- Build FastAPI CRUD endpoints: GET /articles (paginated, filter by category/source/posted), GET /articles/{id}, PATCH /articles/{id}/post
- Build a minimal admin dashboard (HTML + Jinja2 or plain JSON responses) to view pipeline state, article counts, and manually trigger a scrape
- Implement `services/telegram_poster.py` to format and send articles to the Telegram channel using the Bot API
- Wire APScheduler to run `run_scrapers()` + classify + post cycle on the configured interval
- Write end-to-end tests covering: scrape → classify → post flow, duplicate detection, Telegram message format

## Acceptance Criteria

**Functional behavior:**
The bot must run fully unattended — on every scheduled tick it scrapes both sources, classifies new articles by keyword, rewrites each article via the AI API, and posts the result to the configured Telegram channel. Duplicate articles must never be posted twice. The admin endpoint must return current article counts by category and source.

**Performance metrics:**
- CoinTelegraph scrape cycle completes in under 60 seconds for 10 articles
- Blockworks scrape cycle completes in under 120 seconds for 10 articles (DrissionPage warm session target)
- Classifier processes 20 articles in under 1 second
- Telegram post delivers within 5 seconds of the scrape cycle completing
- Zero duplicate posts across consecutive scheduler runs

**Tests written:**
- `tests/test_scraper.py` — mock HTTP responses, assert article dict shape and field types
- `tests/test_classifier.py` — assert correct category assigned per keyword set
- `tests/test_dedup.py` — assert DuplicateKeyError path skips without raising
- `tests/test_telegram.py` — mock Bot API, assert message format and channel ID

**Reviewed & deployed:**
Code reviewed locally against the day plan files (`plan/day2.md`, `plan/day3.md`, `plan/day4.md`). Deployed as a continuously running Python process on the local machine first, then moved to a Linux VPS or cloud instance for always-on operation.

## Checkboxes

- [x] Day 1 — Scraper layer complete (CoinTelegraph + Blockworks + MongoDB + 3-layer CF bypass)
- [ ] Day 2 — Data cleaner, classifier, FastAPI CRUD endpoints, admin dashboard
- [ ] Day 3 — Telegram poster, AI rewriter, APScheduler automation
- [ ] Day 3 — DrissionPage Layer 3 investigation and implementation for Blockworks full content
- [ ] Day 4 — End-to-end tests, error handling hardening, duplicate post guard
- [ ] Day 4 — Deploy to always-on environment and confirm scheduled cycle runs unattended

## Daily Progress

**[Mon Jun 16]:** Completed Day 1 fully. Scrapers operational for both sources. MongoDB Atlas connected with 22 clean articles stored. Verbose debug logging added across all layers. Diagnosed Cloudflare Turnstile as the root cause of Blockworks content limitation (two-layer CF protection confirmed). DrissionPage identified as the next bypass strategy. Day 2 not yet started.

**[Tue Jun 17]:** 
