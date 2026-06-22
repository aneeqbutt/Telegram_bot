import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
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
    <p>Bitcoin surpassed $100,000 for the first time today as institutional demand grew significantly across all major markets.</p>
    <p>The milestone was reached after months of steady accumulation by spot ETF funds from BlackRock, Fidelity, and other major asset managers globally.</p>
    <p>Analysts widely expect this level to become a major psychological support zone going forward in the current market cycle.</p>
    <p>On-chain data shows long-term holders have not sold into this rally, suggesting strong conviction among experienced investors.</p>
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


async def test_cointelegraph_returns_articles():
    scraper = CoinTelegraphScraper()
    with patch.object(scraper, "fetch_page", side_effect=[SAMPLE_RSS, SAMPLE_ARTICLE_HTML]):
        results = await scraper.scrape()
    assert len(results) == 1
    assert results[0]["title"] == "Bitcoin hits $100K"
    assert results[0]["source_name"] == "CoinTelegraph"
    assert len(results[0]["content"]) >= 50


def test_cointelegraph_article_has_required_keys(sample_article):
    required_keys = {"title", "url", "content", "published_at", "source_name"}
    assert required_keys.issubset(sample_article.keys())


async def test_blockworks_returns_articles():
    scraper = BlockworksScraper()
    mock_response = MagicMock()
    mock_response.json.return_value = BLOCKWORKS_API_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        results = await scraper.scrape()

    assert len(results) == 1
    assert results[0]["source_name"] == "Blockworks"
    assert "content" in results[0]


def test_blockworks_parse_date_iso():
    scraper = BlockworksScraper()
    result = scraper._parse_date("2026-06-17T10:00:00Z")
    assert isinstance(result, datetime)
    assert result.year == 2026


def test_blockworks_parse_date_rfc2822():
    scraper = BlockworksScraper()
    result = scraper._parse_date("Tue, 17 Jun 2026 10:00:00 GMT")
    assert isinstance(result, datetime)
    assert result.month == 6


def test_blockworks_parse_date_fallback():
    scraper = BlockworksScraper()
    result = scraper._parse_date(None)
    assert isinstance(result, datetime)
