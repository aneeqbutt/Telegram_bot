import pytest
from services.classifier import classify_article, load_keywords
import services.classifier as classifier_module


@pytest.fixture(autouse=True)
def reset_keyword_map():
    # Reset the in-memory cache before each test so tests don't bleed into each other
    original = classifier_module._keyword_map.copy()
    yield
    classifier_module._keyword_map = original


async def test_classify_bitcoin_article(mock_db):
    await load_keywords(mock_db)
    category = classify_article(
        title="Bitcoin hits $100K for first time",
        content="The price of bitcoin surged past one hundred thousand dollars."
    )
    assert category == "Bitcoin"


async def test_classify_ethereum_article(mock_db):
    await load_keywords(mock_db)
    category = classify_article(
        title="Ethereum upgrade approved by developers",
        content="The ethereum network will undergo a major protocol upgrade next month."
    )
    assert category == "Ethereum"


async def test_classify_title_weighted_higher(mock_db):
    await load_keywords(mock_db)
    # Title has "bitcoin", body has no crypto keywords — title 2x weight should still classify as Bitcoin
    category = classify_article(
        title="Bitcoin dominance grows strongly",
        content="Markets are rallying as institutional demand continues to build across all asset classes."
    )
    assert category == "Bitcoin"


async def test_classify_uncategorized_when_no_match(mock_db):
    await load_keywords(mock_db)
    category = classify_article(
        title="Stock markets surge to record highs",
        content="The S&P 500 hit a record high today as tech stocks rallied strongly."
    )
    assert category == "Uncategorized"


def test_classify_empty_cache_returns_uncategorized():
    classifier_module._keyword_map = {}
    category = classify_article("Bitcoin news", "Bitcoin price analysis")
    assert category == "Uncategorized"
