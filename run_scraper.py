import asyncio
import sys
from database.db import connect_db, disconnect_db


async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_scraper.py [cointelegraph | blockworks]")
        return

    scraper_name = sys.argv[1].lower().strip()
    await connect_db()

    try:
        if scraper_name == "cointelegraph":
            from scrapers.cointelegraph import CoinTelegraphScraper
            scraper = CoinTelegraphScraper()
        elif scraper_name == "blockworks":
            from scrapers.blockworks import BlockworksScraper
            scraper = BlockworksScraper()
        else:
            print(f"Unknown scraper: {scraper_name}")
            return

        from database.db import get_db
        from services.classifier import load_keywords, classify_article
        from utils.cleaner import clean_article
        db = get_db()
        await load_keywords(db)

        print(f"Running {scraper_name} scraper...")
        results = await scraper.scrape(limit=5)
        print(f"\n--- Scraped {len(results)} articles ---")
        for r in results:
            cleaned = clean_article(r)
            category = classify_article(cleaned["title"], cleaned["content"])
            print(f"- [{category}] {cleaned['title']} ({cleaned['url']})")
    except Exception as e:
        print(f"Error running scraper: {e}")
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
