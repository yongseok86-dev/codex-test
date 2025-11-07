import asyncio
import json
from httpx import AsyncClient, Timeout


async def main():
    params = {
        "q": "디바이스별 시간대별 방문자 수",
        "limit": 10,
        "dry_run": True,
        "use_llm": False,
    }
    # Increase timeout to 60 seconds
    timeout = Timeout(60.0, connect=10.0)

    try:
        async with AsyncClient(base_url="http://localhost:8080", timeout=timeout) as ac:
            async with ac.stream("GET", "/api/query/stream", params=params) as r:
                print(f"status={r.status_code}\n")
                try:
                    async for line in r.aiter_lines():
                        if not line or line.strip() == "":
                            continue
                        print(line)
                except Exception as e:
                    print(f"\nStream ended or timeout: {type(e).__name__}: {e}")
                    print("\n--- Received data successfully (stream may have ended) ---")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

