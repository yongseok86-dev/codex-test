import asyncio
import json
from httpx import AsyncClient


async def main():
    params = {
        "q": "지난 7일 주문 추이",
        "limit": 10,
        "dry_run": True,
        "use_llm": False,
    }
    async with AsyncClient(app=None, base_url="http://localhost:8080") as ac:
        async with ac.stream("GET", "/api/query/stream", params=params) as r:
            print(f"status={r.status_code}")
            async for line in r.aiter_lines():
                if line is None:
                    continue
                print(line)


if __name__ == "__main__":
    asyncio.run(main())

