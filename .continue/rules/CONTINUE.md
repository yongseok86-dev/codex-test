# CONTINUE.md: Project Guide

## 1. Project Overview

**Purpose:**
이 프로젝트는 Vue.js 3, TypeScript, Element Plus를 기반으로 한 AI 검수 관리 시스템의 프론트엔드 애플리케이션입니다. 주요 기능은 AI 자료 검수, 관리자 기능(배너, FAQ, 공지, 권한 등), 사용자 인증, 활동 로그 및 대시보드를 포함합니다.

**주요 기술:**
- Vue.js 3 (Composition API)
- TypeScript
- Element Plus (UI 라이브러리)
- Pinia (상태 관리)
- Vite (빌드 시스템)
- SCSS (스타일링)
- Auto Import

**아키텍처:**
모듈 분리형 SPA (Single Page Application)로, 각 도메인별 모델/서비스/스토어/뷰(페이지)가 체계적으로 분리되어 확장성과 유지보수성을 높였습니다.

---

## 2. Getting Started

**Prerequisites:**
- Node.js 16.x 이상
- npm (또는 yarn 등)

**설치 및 실행:**
```bash
npm install           # 의존성 설치
npm run dev           # 개발 서버 실행 (기본 포트 8000)
npm run build         # 프로덕션 빌드
npm run preview       # 빌드 결과 미리보기
```

**테스트:**
(테스트 도구 및 위치 미정: 실제 tests/ 폴더 사용시 예시)
```bash
npm test              # 또는
pytest -q             # Python 백엔드 연동 사용시
```

---

## 3. Project Structure

- `src/assets/`: 전역 스타일, 이미지 및 폰트 등 정적 자산
- `src/components/`: 재사용 View 컴포넌트(도메인별/팝업/레이아웃 등)
- `src/composables/`: Composition API 기반 재사용 로직
- `src/Layout/`: 전체 페이지 레이아웃
- `src/model/`: 도메인별 API/데이터 모델
- `src/router/`: 라우팅 구성
- `src/services/`: 서비스 계층(API 통신, 인증 등)
- `src/stores/`: 상태(Pinia) 관리용 스토어
- `src/types/`: 타입/인터페이스 정의
- `src/utils/`: 범용 유틸리티
- `src/views/`: 페이지 UI 및 논리 구현
- `public/`, `index.html`: 정적 공개 자원/SPA entrypoint

**주요 설정 파일:**
- `package.json`, `tsconfig.json`, `vite.config.js`
- `.prettierrc`, `.gitignore`

---

## 4. Development Workflow

- **코딩 컨벤션:**
  - TypeScript, Composition API, Pinia, SCSS 스타일 격리
  - 파일/컴포넌트 구조: 도메인 우선, 역할별 분리, 타입 엄수
- **테스트:**
  - (테스트 폴더/프레임워크는 실제 구성 확인 필요)
- **빌드/배포:**
  - Vite 기반 빌드
  - CI/CD는 별도 구성(README/운영자 확인 필요)
- **기여 가이드:**
  - 브랜치 전략/PR 리뷰/Commit 메시지 표준(Conventional Commits 권장)
  - 주요 규칙은 README 가이드 및 CLAUDE_PROJECT_GUIDE.md 참고

---

## 5. Key Concepts

- **AI Agent:** 검수 요청의 기록/분석/결과 제공까지의 전체 흐름
- **관리도메인:** 콘텐츠(배너, FAQ, Notice 등) 관리 전반
- **권한/인증:** 사용자별 접근 제한/2FA 지원 등
- **Reusable Composition:** composables로 로직 분리 및 재활용
- **SPA Routing:** 페이지와 메뉴/권한/탭 분리 및 이동

---

## 6. Common Tasks

- **새 컴포넌트 추가:**
  1. `src/components/` (또는 views/ 대상 위치) 신규 파일 생성
  2. 자동 import가 필요한 경우 규칙 적용
- **새 페이지/라우트 추가:**
  1. `src/views/`에 Vue 파일 생성
  2. `src/router/index.ts`에 route 등록 및 meta 정보 작성
  3. 접근 메뉴의 경우 관리자 메뉴 관리 or 메뉴 DB도 반영
- **상태 관리:**
  - Pinia 스토어 생성(예: `src/stores/alert.ts`)
- **API 통신:**
  1. `src/services/`에 서비스 추가
  2. 모델/유틸리티와 인터페이스 설계(타입 일치 주의)

---

## 7. Troubleshooting

- **빌드/런 오류:**
  - Node/NPM 버전 확인, 의존성 재설치
  - 포트 충돌: `vite.config.js`에서 포트 변경
- **권한/라우터 오류:**
  - 권한 미지정시 접근 차단, 관리자 메뉴 구성 확인
- **스타일 문제:**
  - SCSS 변수/전역 스타일 확인, 혹시 중복 스타일로 인한 충돌
- **자동 import 미작동:**
  - `unplugin-auto-import`, `unplugin-vue-components` 설정 오류 여부 점검

---

## 8. References

- [Vue.js 공식 문서](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
- [Vite](https://vitejs.dev/)
- [Pinia](https://pinia.vuejs.org/)
- 프로젝트 자체 문서: `README.md`, `CLAUDE_PROJECT_GUIDE.md`, `docs/structure-analysis.md`


---

> ⚠️ 일부 상세 사항(예: 테스트 폴더, CI/CD, DB/ API 상세)은 실제 코드/운영 환경 확인과 담당자 검토가 필요합니다. 실사용 과정에서 발견되는 추가 정보는 이 파일 내에 계속 업데이트하시기 바랍니다.
