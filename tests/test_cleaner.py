from utils.cleaner import clean_html, normalize_url, normalize_timestamp, clean_article
from datetime import datetime


def test_clean_html_strips_tags():
    assert clean_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_clean_html_collapses_whitespace():
    result = clean_html("<p>  too   many   spaces  </p>")
    assert "  " not in result
    assert "too" in result


def test_clean_html_handles_empty_string():
    assert clean_html("") == ""


def test_clean_html_handles_none():
    assert clean_html(None) == ""


def test_normalize_url_strips_query_params():
    url = "https://cointelegraph.com/news/bitcoin-100k?ref=twitter&utm_source=rss"
    assert normalize_url(url) == "https://cointelegraph.com/news/bitcoin-100k"


def test_normalize_url_lowercases():
    result = normalize_url("https://CoinTelegraph.com/News/BTC")
    assert result == "https://cointelegraph.com/news/btc"


def test_normalize_url_strips_trailing_slash():
    result = normalize_url("https://cointelegraph.com/news/bitcoin/")
    assert not result.endswith("/")


def test_normalize_timestamp_passes_through_naive_datetime():
    dt = datetime(2026, 6, 17, 10, 0, 0)
    result = normalize_timestamp(dt)
    assert isinstance(result, datetime)
    assert result.year == 2026


def test_clean_article_strips_html_from_content():
    raw = {
        "title": "  Bitcoin ETF  ",
        "url": "https://example.com/news?ref=rss",
        "content": "<p>Bitcoin hit <b>$100K</b></p>",
        "published_at": datetime(2026, 6, 17),
        "source_name": "CoinTelegraph"
    }
    cleaned = clean_article(raw)
    assert "<p>" not in cleaned["content"]
    assert "<b>" not in cleaned["content"]
    assert "Bitcoin hit" in cleaned["content"]


def test_clean_article_strips_query_params_from_url():
    raw = {
        "title": "Test",
        "url": "https://example.com/news?ref=rss",
        "content": "Some content here.",
        "published_at": datetime(2026, 6, 17),
        "source_name": "Test"
    }
    cleaned = clean_article(raw)
    assert "ref=rss" not in cleaned["url"]


def test_clean_article_trims_title():
    raw = {
        "title": "  Bitcoin ETF  ",
        "url": "https://example.com/news",
        "content": "Content.",
        "published_at": datetime(2026, 6, 17),
        "source_name": "Test"
    }
    cleaned = clean_article(raw)
    assert cleaned["title"] == "Bitcoin ETF"
