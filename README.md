# codex-test

?„ëŸ°?¸ì—”??ì¶”ê? ?ˆì •): TypeScript + Vue3 + Element Plus  
ë°±ì—”??êµ¬í˜„??: FastAPI ê¸°ë°˜ NL?’SQL BigQuery ?œë©˜???ˆì´???ì´?„íŠ¸ ?¤ìº?´ë“œ

## ?„ë¡œ?íŠ¸ êµ¬ì„±
- `app/` ??FastAPI ??  - `main.py` ???”íŠ¸ë¦? ë¯¸ë“¤?¨ì–´
  - `routers/` `health.py`, `query.py`
  - `services/` `nlu.py`, `planner.py`, `sqlgen.py`, `validator.py`, `executor.py`
  - `semantic/` `semantic.yml`, `metrics_definitions.yaml`
  - `utils/` `timeparse.py`
- `tests/` ??ê¸°ë³¸ ?ŒìŠ¤??(`pytest`)
- `.github/` ??CI, PR ?œí”Œë¦? CODEOWNERS

## ?œì‘?˜ê¸° (ë¡œì»¬ ê°œë°œ)
?¬ì „ì¡°ê±´: Python 3.11+, pip(?ëŠ” uv), Git

1) ?¤ì¹˜
- `pip install -e .[dev]`

2) ?¤í–‰
- `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- ?¬ìŠ¤ì²´í¬: `GET /healthz`, `GET /readyz`
- ì§ˆì˜ ?ˆì‹œ: `POST /api/query` ë°”ë”” `{ "q": "ì§€??7??ì£¼ë¬¸ ì¶”ì´" }`

3) ?ŒìŠ¤??- `pytest -q`

### ?„ëŸ°?¸ì—”??ChatGPT ?¤í???UI)
- ?„ì¹˜: `frontend/`
- ?¤ì¹˜: `cd frontend && npm ci`
- ê°œë°œ ?œë²„: `npm run dev` (ê¸°ë³¸ http://localhost:5173)
- ë°±ì—”???„ë¡?? `vite.config.ts`?ì„œ `/api`ë¥?`http://localhost:8080`?¼ë¡œ ?„ë¡??
## ?˜ê²½(.env) ?¤ì •
ê¸°ë³¸ê°’ì? ?ˆì „ëª¨ë“œ(?œë¼?´ëŸ°)?…ë‹ˆ?? ?„ìš” ??`.env`ë¥?ì¶”ê??˜ì„¸??

?ˆì‹œ `.env`:
```
env=dev
gcp_project=your-gcp-project
bq_default_location=asia-northeast3
maximum_bytes_billed=5000000000
dry_run_only=true
```

BigQuery ?¤ì œ ?¤í–‰ ?œì—??GCP ?¸ì¦???„ìš”?©ë‹ˆ??
- `GOOGLE_APPLICATION_CREDENTIALS`???œë¹„??ê³„ì • ??ê²½ë¡œ ?¤ì •
- ?ëŠ” ?°í????˜ê²½(Cloud Run ????ê¸°ë³¸ ?¸ì¦ ?œê³µ

?„ëŸ°?¸ì—”?œëŠ” ì¶”í›„ `frontend/` ?”ë ‰?°ë¦¬??Vue3 ê¸°ë°˜?¼ë¡œ ì¶”ê????ˆì •?…ë‹ˆ??

## Streaming API (SSE)
- ?”ë“œ?¬ì¸?? `GET /api/query/stream?q=...&limit=...&dry_run=...`
- ?´ë²¤???ë¦„: `nlu` ??`plan` ??`sql` ??`validated` ??`result`
- ?„ëŸ°?¸ì—”?œëŠ” ê¸°ë³¸?ìœ¼ë¡??¤íŠ¸ë¦¬ë° ëª¨ë“œê°€ ?œì„±?”ë˜???¨ê³„ë³?ì§„í–‰ ?í™©???œì‹œ?©ë‹ˆ??

## LLM ±â¹İ SQL »ı¼º
- ¼³Á¤(.env):
  - llm_provider=openai
  - openai_api_key=sk-...
  - openai_model=gpt-4o-mini (¼±ÅÃ)
- »ç¿ë:
  - REST: POST /api/query { q, use_llm: true, dry_run, limit }
  - SSE: GET /api/query/stream?q=...&use_llm=true
- ½Ã¸àÆ½ ·¹ÀÌ¾î(semantic.yml, metrics_definitions.yaml)¸¦ ÇÁ·ÒÇÁÆ®¿¡ ÁÖÀÔÇÏ¿© Á¤È®µµ Çâ»ó.


## È¯°æ ÅÛÇÃ¸´
- ·çÆ®ÀÇ `.env.example`¸¦ º¹»çÇØ `.env`·Î »ç¿ëÇÏ¼¼¿ä. GCP/BigQuery ¹× LLM(openai/claude/gemini) ¼³Á¤ Å°¸¦ Ã¤¿î µÚ ¼­¹ö¸¦ Àç½ÃÀÛÇÏ¸é Àû¿ëµË´Ï´Ù.

