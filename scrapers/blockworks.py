# Scraper for Blockworks.
# Blockworks' own frontend React app fetches articles from an internal JSON endpoint.
# That endpoint has no Cloudflare protection on it, so we hit it directly and get
# 50 articles with full content in one single HTTP call — no HTML parsing, no page visits.
# One request → 50 articles done.

import httpx
from datetime import datetime
from scrapers.base_scraper import BaseScraper

BLOCKWORKS_API = "https://blockworks.com/api/posts"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Number of latest articles to request from the API in a single call
BLOCKWORKS_API_LIMIT = 50


class BlockworksScraper(BaseScraper):

    async def scrape(self) -> list[dict]:
        # Calls the Blockworks API and returns all articles from the JSON response
        self.logger.info(f"Starting Blockworks scrape via API ({BLOCKWORKS_API})...")

        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
                response = await client.get(BLOCKWORKS_API, params={"limit": BLOCKWORKS_API_LIMIT})
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Blockworks API returned HTTP {e.response.status_code}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Blockworks API request failed: {e}")
            return []

        # Handle different possible response shapes (list or dict with a posts/data key)
        posts = data if isinstance(data, list) else data.get("posts") or data.get("data") or data.get("articles") or []

        if not posts:
            self.logger.warning(f"Blockworks API returned no posts. Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return []

        self.logger.info(f"Blockworks API returned {len(posts)} posts. Processing all...")

        articles = []
        for post in posts:
            title = post.get("title") or post.get("headline") or "No Title"

            # Try multiple possible URL field names in the API response
            url = (
                post.get("permalink")
                or post.get("url")
                or post.get("link")
                or post.get("canonical_url")
            )
            if not url:
                slug = post.get("slug")
                if slug:
                    url = f"https://blockworks.co/news/{slug}"
            if not url:
                self.logger.warning(f"No URL found for post '{title}' — skipping")
                continue

            if not url.startswith("http"):
                url = f"https://blockworks.co{url}"

            # Try multiple possible content field names in the API response
            content = (
                post.get("content")
                or post.get("body")
                or post.get("html")
                or post.get("excerpt")
                or post.get("summary")
                or ""
            )

            if not content:
                self.logger.warning(f"No content field found for '{title}' — skipping")
                continue

            self.logger.debug(f"[API] '{title[:60]}' — {len(content)} chars raw content")

            # Try multiple possible date field names in the API response
            raw_date = (
                post.get("publishedAt")
                or post.get("published_at")
                or post.get("date")
                or post.get("createdAt")
            )
            published_at = self._parse_date(raw_date)

            articles.append({
                "title": title,
                "url": url,
                "content": content,
                "published_at": published_at,
                "source_name": "Blockworks",
            })

        self.logger.info(f"Blockworks: {len(articles)} articles ready from API response")
        return articles

    def _parse_date(self, raw) -> datetime:
        # Converts API date strings to a UTC datetime object.
        # Handles both ISO 8601 ("2026-01-07T14:00:00Z") and RFC 2822 ("Wed, 07 Jan 2026 14:00:00 GMT").
        if not raw:
            return datetime.utcnow()
        if isinstance(raw, datetime):
            return raw.replace(tzinfo=None) if raw.tzinfo else raw
        raw_str = str(raw).strip()

        # Try ISO 8601 first
        try:
            dt = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            pass

        # Try RFC 2822 (GMT suffix → +0000 so strptime can handle the timezone)
        try:
            normalized = raw_str.replace("GMT", "+0000")
            dt = datetime.strptime(normalized, "%a, %d %b %Y %H:%M:%S %z")
            return dt.replace(tzinfo=None)
        except Exception:
            pass

        self.logger.warning(f"Could not parse date '{raw}' — using utcnow()")
        return datetime.utcnow()
