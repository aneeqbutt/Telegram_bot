# Base class for all scrapers.
# Provides a shared fetch_page() method using httpx.
# If Cloudflare blocks the request, raises an exception so the calling
# scraper can fall back to its RSS/summary fallback instead.

import httpx
from abc import ABC, abstractmethod
from utils.logger import get_logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# HTTP status codes Cloudflare returns when it blocks a request
CLOUDFLARE_STATUS_CODES = {403, 503, 429, 520, 521, 522, 523, 524}


class BaseScraper(ABC):
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    async def fetch_page(self, url: str) -> str:
        # Fetches a URL with httpx. Raises on Cloudflare blocks so the
        # scraper's except block can trigger its RSS fallback.
        async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
            response = await client.get(url, follow_redirects=True)

        if response.status_code in CLOUDFLARE_STATUS_CODES:
            self.logger.warning(f"[httpx] Cloudflare blocked {url} (status {response.status_code})")
            raise httpx.HTTPStatusError(
                f"Cloudflare block: {response.status_code}",
                request=response.request,
                response=response,
            )

        response.raise_for_status()
        self.logger.debug(f"[httpx] OK ({response.status_code}) {url} — {len(response.text)} bytes")
        return response.text

    @abstractmethod
    async def scrape(self) -> list[dict]:
        # Every child scraper must implement this and return a list of article dicts
        # with keys: title, url, content, published_at, source_name
        pass
