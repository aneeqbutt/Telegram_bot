import pytest
from unittest.mock import AsyncMock, MagicMock
from pymongo.errors import DuplicateKeyError
from database import crud


async def test_article_exists_returns_true_when_found():
    db = MagicMock()
    db.articles.find_one = AsyncMock(return_value={"_id": "abc123"})
    result = await crud.article_exists(db, "https://example.com/news/bitcoin")
    assert result is True


async def test_article_exists_returns_false_when_not_found():
    db = MagicMock()
    db.articles.find_one = AsyncMock(return_value=None)
    result = await crud.article_exists(db, "https://example.com/news/new-article")
    assert result is False


async def test_insert_article_returns_none_on_duplicate():
    db = MagicMock()
    db.articles.insert_one = AsyncMock(side_effect=DuplicateKeyError(""))
    result = await crud.insert_article(db, {"url": "https://example.com/already-exists"})
    assert result is None


async def test_insert_article_returns_id_on_success():
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.inserted_id = "newid123"
    db.articles.insert_one = AsyncMock(return_value=mock_result)
    result = await crud.insert_article(db, {"url": "https://example.com/new"})
    assert result == "newid123"
