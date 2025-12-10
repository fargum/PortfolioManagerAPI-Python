import asyncio
from src.db.session import AsyncSessionLocal
from sqlalchemy import text

async def test():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text('SELECT 1'))
        print('DB OK:', result.scalar())

asyncio.run(test())
