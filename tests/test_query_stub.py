from httpx import AsyncClient
from app.main import app


async def test_query_stub():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/api/query", json={"q": "지난 7일 주문 추이"})
    assert r.status_code == 200
    body = r.json()
    assert "SELECT" in body["sql"].upper()
    assert body["dry_run"] is True

