import sys
import os

# Add root path to sys.path to allow running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pymongo import MongoClient, ASCENDING
from utils.config import MONGODB_URI, DB_NAME
from utils.logger import get_logger

logger = get_logger("init_db")

def init_database():
    if not MONGODB_URI:
        logger.error("MONGODB_URI environment variable is not set!")
        sys.exit(1)

    logger.info(f"Connecting to MongoDB database '{DB_NAME}' using PyMongo...")
    try:
        import certifi
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
        db = client[DB_NAME]
        
        # Verify connection by triggering a command
        client.admin.command("ping")
        logger.info("Successfully connected to MongoDB server.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB server: {e}")
        logger.error("Please make sure MongoDB is running and MONGO_URI in .env is correct.")
        sys.exit(1)
    
    # 1. Create collections and indexes
    logger.info("Setting up collections and indexes...")
    
    # Articles
    logger.info("Setting up 'articles' indexes...")
    db.articles.create_index([("url", ASCENDING)], unique=True)
    db.articles.create_index([("is_posted", ASCENDING)])
    db.articles.create_index([("published_at", ASCENDING)])
    db.articles.create_index([("scraped_at", ASCENDING)])
    
    # Sources
    logger.info("Setting up 'sources' indexes...")
    db.sources.create_index([("base_url", ASCENDING)], unique=True)
    
    # Categories
    logger.info("Setting up 'categories' indexes...")
    db.categories.create_index([("name", ASCENDING)], unique=True)
    
    # Channels
    logger.info("Setting up 'channels' indexes...")
    db.channels.create_index([("telegram_id", ASCENDING)], unique=True)
    
    # Logs
    logger.info("Setting up 'logs' indexes...")
    db.logs.create_index([("posted_at", ASCENDING)])
    db.logs.create_index([("article_id", ASCENDING)])
    
    # 2. Seed data
    logger.info("Seeding initial data...")
    
    # Seed Sources
    sources_data = [
        { "name": "CoinTelegraph", "base_url": "https://cointelegraph.com", "is_active": True },
        { "name": "Blockworks", "base_url": "https://blockworks.co/news", "is_active": True }
    ]
    for source in sources_data:
        try:
            db.sources.update_one(
                {"base_url": source["base_url"]},
                {"$setOnInsert": source},
                upsert=True
            )
            logger.info(f"Upserted source: {source['name']}")
        except Exception as e:
            logger.error(f"Error seeding source {source['name']}: {e}")
            
    # Seed Categories
    categories_data = [
        { "name": "Bitcoin", "description": "BTC news", "is_active": True },
        { "name": "Ethereum", "description": "ETH news", "is_active": True },
        { "name": "DeFi", "description": "Decentralized finance", "is_active": True },
        { "name": "Regulation", "description": "Crypto regulation and policy", "is_active": True },
        { "name": "NFT", "description": "Non-fungible tokens", "is_active": True },
        { "name": "Uncategorized", "description": "Default fallback", "is_active": True }
    ]
    for category in categories_data:
        try:
            db.categories.update_one(
                {"name": category["name"]},
                {"$setOnInsert": category},
                upsert=True
            )
            logger.info(f"Upserted category: {category['name']}")
        except Exception as e:
            logger.error(f"Error seeding category {category['name']}: {e}")
            
    # Seed Keywords
    keywords_data = [
        { "word": "bitcoin", "category_name": "Bitcoin", "weight": 1 },
        { "word": "btc", "category_name": "Bitcoin", "weight": 1 },
        { "word": "ethereum", "category_name": "Ethereum", "weight": 1 },
        { "word": "eth", "category_name": "Ethereum", "weight": 1 },
        { "word": "defi", "category_name": "DeFi", "weight": 1 },
        { "word": "decentralized finance", "category_name": "DeFi", "weight": 1 },
        { "word": "sec", "category_name": "Regulation", "weight": 1 },
        { "word": "regulation", "category_name": "Regulation", "weight": 1 },
        { "word": "nft", "category_name": "NFT", "weight": 1 },
        { "word": "non-fungible", "category_name": "NFT", "weight": 1 }
    ]
    # We can create a unique index on keywords (word, category_name) to avoid duplicates
    db.keywords.create_index([("word", ASCENDING), ("category_name", ASCENDING)], unique=True)
    
    for kw in keywords_data:
        try:
            db.keywords.update_one(
                {"word": kw["word"], "category_name": kw["category_name"]},
                {"$setOnInsert": kw},
                upsert=True
            )
            logger.info(f"Upserted keyword: {kw['word']} -> {kw['category_name']}")
        except Exception as e:
            logger.error(f"Error seeding keyword {kw['word']}: {e}")
            
    logger.info("Database initialization completed successfully!")
    client.close()

if __name__ == "__main__":
    init_database()
