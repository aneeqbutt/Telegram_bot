# Data cleaning utilities applied to every article before it is stored in MongoDB.
# Ensures consistent, plain-text content across both scrapers regardless of their raw output format.

from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import datetime, timezone
import re
from urllib.parse import urlparse, urlunparse


def clean_html(text: str) -> str:
    # Strips all HTML tags from a string and collapses extra whitespace into single spaces.
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    clean = soup.get_text(separator=" ")
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def normalize_timestamp(raw) -> datetime:
    # Converts any timestamp format (string, datetime with timezone, etc.) to a UTC datetime with no tzinfo.
    if isinstance(raw, datetime):
        if raw.tzinfo is not None:
            return raw.astimezone(timezone.utc).replace(tzinfo=None)
        return raw
    try:
        dt = dateparser.parse(str(raw))
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.utcnow()


def normalize_url(url: str) -> str:
    # Lowercases the URL and strips query params, fragments, and trailing slashes
    # so that duplicate articles from different tracking links are caught by the unique index.
    parsed = urlparse(url.lower().strip())
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', '', ''))
    return clean


def clean_article(article: dict) -> dict:
    # Runs all cleaners on a raw scraper output dict and returns the cleaned version.
    return {
        **article,
        "url": normalize_url(article.get("url", "")),
        "title": article.get("title", "").strip(),
        "content": clean_html(article.get("content", "")),
        "published_at": normalize_timestamp(article.get("published_at")),
    }
