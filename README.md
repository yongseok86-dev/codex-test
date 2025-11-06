# codex-test

프런트엔드(추가 예정): TypeScript + Vue3 + Element Plus  
백엔드(구현됨): FastAPI 기반 NL→SQL BigQuery 시멘틱 레이어 에이전트 스캐폴드

## 프로젝트 구성
- `app/` – FastAPI 앱
  - `main.py` 앱 엔트리, 미들웨어
  - `routers/` `health.py`, `query.py`
  - `services/` `nlu.py`, `planner.py`, `sqlgen.py`, `validator.py`, `executor.py`
  - `semantic/` `semantic.yml`, `metrics_definitions.yaml`
  - `utils/` `timeparse.py`
- `tests/` – 기본 테스트 (`pytest`)
- `.github/` – CI, PR 템플릿, CODEOWNERS

## 시작하기 (로컬 개발)
사전조건: Python 3.11+, pip(또는 uv), Git

1) 설치
- `pip install -e .[dev]`

2) 실행
- `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- 헬스체크: `GET /healthz`, `GET /readyz`
- 질의 예시: `POST /api/query` 바디 `{ "q": "지난 7일 주문 추이" }`

3) 테스트
- `pytest -q`

### 프런트엔드(ChatGPT 스타일 UI)
- 위치: `frontend/`
- 설치: `cd frontend && npm ci`
- 개발 서버: `npm run dev` (기본 http://localhost:5173)
- 백엔드 프록시: `vite.config.ts`에서 `/api`를 `http://localhost:8080`으로 프록시

## 환경(.env) 설정
기본값은 안전모드(드라이런)입니다. 필요 시 `.env`를 추가하세요.

예시 `.env`:
```
env=dev
gcp_project=your-gcp-project
bq_default_location=asia-northeast3
maximum_bytes_billed=5000000000
dry_run_only=true
```

BigQuery 실제 실행 시에는 GCP 인증이 필요합니다.
- `GOOGLE_APPLICATION_CREDENTIALS`에 서비스 계정 키 경로 설정
- 또는 런타임 환경(Cloud Run 등)에 기본 인증 제공

프런트엔드는 추후 `frontend/` 디렉터리에 Vue3 기반으로 추가할 예정입니다.
