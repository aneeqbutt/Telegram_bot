import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.ai_rewriter import rewrite_article, _truncate_fallback


def test_truncate_fallback_cuts_at_sentence():
    content = "First sentence is here. Second sentence continues. Third sentence is the longest one of all."
    result = _truncate_fallback(content, max_chars=50)
    assert result.endswith(".")
    assert len(result) <= 50


def test_truncate_fallback_returns_as_is_when_short():
    short = "Short content."
    assert _truncate_fallback(short) == short


def test_truncate_fallback_adds_ellipsis_when_no_sentence_found():
    # No period in the first half — should add ellipsis
    content = "A" * 900
    result = _truncate_fallback(content)
    assert result.endswith("...")
    assert len(result) <= 803  # 800 + "..."


async def test_rewrite_article_calls_openrouter():
    # Mock the OpenRouter response format (choices[0].message.content)
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Rewritten crypto news summary."}}]
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        with patch("services.ai_rewriter.AI_API_KEY", "test-key"):
            result = await rewrite_article("Bitcoin news", "Long article content here.")

    assert result == "Rewritten crypto news summary."


async def test_rewrite_article_uses_fallback_on_api_failure():
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("Network error")
        )
        with patch("services.ai_rewriter.AI_API_KEY", "test-key"):
            result = await rewrite_article("Bitcoin news", "Some content that is short enough.")

    assert "Some content" in result


async def test_rewrite_article_uses_fallback_when_no_api_key():
    with patch("services.ai_rewriter.AI_API_KEY", None):
        result = await rewrite_article("Bitcoin news", "Content for the article.")

    assert len(result) > 0
