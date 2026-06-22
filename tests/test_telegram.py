import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.telegram_poster import format_message, send_message, _escape_html


def test_escape_html_escapes_ampersand():
    assert _escape_html("BTC & ETH") == "BTC &amp; ETH"


def test_escape_html_escapes_less_than():
    assert _escape_html("price < $100K") == "price &lt; $100K"


def test_escape_html_escapes_greater_than():
    assert _escape_html("price > $100K") == "price &gt; $100K"


def test_escape_html_escapes_tags():
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


def test_format_message_escapes_ampersand_in_title():
    msg = format_message(
        title="BTC & ETH rise",
        content="Markets surging.",
        url="https://example.com",
        source_name="Test",
        category="Bitcoin"
    )
    assert "&amp;" in msg
    assert "BTC & ETH" not in msg


async def test_send_message_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 42}}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await send_message("Test message")

    assert result["message_id"] == 42


async def test_send_message_retries_on_429():
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = MagicMock()
            resp.json.return_value = {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 1"
            }
            return resp
        resp = MagicMock()
        resp.json.return_value = {"ok": True, "result": {"message_id": 99}}
        return resp

    with patch("httpx.AsyncClient") as mock_client:
        with patch("asyncio.sleep", AsyncMock()):
            mock_client.return_value.__aenter__.return_value.post = mock_post
            result = await send_message("Test message")

    assert call_count == 2
    assert result["message_id"] == 99
