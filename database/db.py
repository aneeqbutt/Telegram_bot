# MongoDB connection manager.
# Holds a single Motor client instance shared across the entire app.
# All other modules call get_db() to get the database handle — never create their own client.

from motor.motor_asyncio import AsyncIOMotorClient
from utils.config import MONGODB_URI, DB_NAME
from utils.logger import get_logger
import certifi

logger = get_logger(__name__)

client: AsyncIOMotorClient = None


async def connect_db():
    # Creates the Motor client, verifies the connection with a ping, and logs the result.
    global client
    client = AsyncIOMotorClient(MONGODB_URI, tlsCAFile=certifi.where())
    await client.admin.command("ping")
    logger.info("Connected to MongoDB Atlas")


async def disconnect_db():
    # Closes the Motor client cleanly on app shutdown.
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


def get_db():
    # Returns the database handle for the configured DB_NAME.
    return client[DB_NAME]
