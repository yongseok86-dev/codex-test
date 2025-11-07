import asyncio
from httpx import AsyncClient
from app.main import app


async def collect_sse_events(response, max_events=50):
    events = []
    current = {"event": None, "data": ""}
    async for line in response.aiter_lines():
        if line is None:
            continue
        line = line.strip()
        if not line:
            # end of one SSE event
            if current["event"]:
                events.append({"event": current["event"], "data": current["data"]})
            current = {"event": None, "data": ""}
            if len(events) >= max_events:
                break
            continue
        if line.startswith("event:"):
            current["event"] = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            payload = line.split(":", 1)[1].lstrip()
            current["data"] += payload
    return events


async def test_query_stream_basic():
    async with AsyncClient(app=app, base_url="http://localhost") as ac:
        params = {
            "q": "지난 7일 주문 추이",
            "limit": 10,
            "dry_run": True,
            "use_llm": False,
        }
        async with ac.stream("GET", "/api/query/stream", params=params) as r:
            assert r.status_code == 200
            events = await collect_sse_events(r)

    # Should include core milestones
    types = [e["event"] for e in events]
    assert "nlu" in types
    assert "plan" in types
    assert "sql" in types
    assert "validated" in types
    assert "result" in types

