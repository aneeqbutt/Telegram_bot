import asyncio
from database.db import connect_db, disconnect_db, get_db
from services.dispatcher import dispatch_articles


async def main():
    await connect_db()
    db = get_db()
    result = await dispatch_articles(db)
    print(f"\nResult: {result}")
    await disconnect_db()


asyncio.run(main())
