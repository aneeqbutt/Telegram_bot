import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

SAMPLE_KEYWORDS = [
    {"word": "bitcoin", "category_name": "Bitcoin"},
    {"word": "btc", "category_name": "Bitcoin"},
    {"word": "ethereum", "category_name": "Ethereum"},
    {"word": "eth", "category_name": "Ethereum"},
]


@pytest.fixture
def sample_article():
    return {
        "title": "Bitcoin hits $100K for the first time",
        "url": "https://cointelegraph.com/news/bitcoin-100k",
        "content": "Bitcoin surpassed $100,000 for the first time today as institutional demand continued to grow. The milestone was reached after months of steady accumulation by ETF funds.",
        "published_at": datetime(2026, 6, 17, 10, 0, 0),
        "source_name": "CoinTelegraph"
    }


@pytest.fixture
def sample_blockworks_article():
    return {
        "title": "ETH derivatives reset signals next move",
        "url": "https://blockworks.co/news/eth-derivatives-reset",
        "content": "Ethereum's derivatives market has fully reset after a period of overleveraged longs. Open interest has dropped 40% signaling the market is ready for the next directional move.",
        "published_at": datetime(2026, 6, 17, 12, 0, 0),
        "source_name": "Blockworks"
    }


@pytest.fixture
def mock_db():
    db = MagicMock()

    # Attribute-style access: db.articles, db.logs, etc.
    db.articles.find_one = AsyncMock(return_value=None)
    db.articles.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
    db.articles.update_one = AsyncMock(return_value=None)
    db.logs.insert_one = AsyncMock(return_value=None)

    # Dict-style access: db["keywords"] — used by classifier.load_keywords()
    mock_keywords_cursor = MagicMock()
    mock_keywords_cursor.to_list = AsyncMock(return_value=SAMPLE_KEYWORDS)
    mock_keywords_collection = MagicMock()
    mock_keywords_collection.find.return_value = mock_keywords_cursor
    db.__getitem__ = MagicMock(return_value=mock_keywords_collection)

    return db
