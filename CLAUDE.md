# CLAUDE.md

## 프로젝트

**Newsletter AI** — 매일 아침 국내외 주요 AI 관련 뉴스를 자동으로 수집·요약해서 보여주는 웹 애플리케이션.

배포 URL: `https://newsletter-ai-saojeong21s-projects.vercel.app`
GitHub: `https://github.com/saojeong21/newsletter_ai`

---

## 기술 스택

| 항목 | 내용 |
|---|---|
| 백엔드 | FastAPI + Jinja2 (SSR) |
| DB | Supabase PostgreSQL (`ainewsletter_items` 테이블) |
| AI 요약 | OpenRouter 무료 모델 폴백 (gemma-3-27b → gemma-3-12b → llama-3.3-70b → mistral-small) |
| 뉴스 수집 | feedparser RSS (활성 10개 소스, 국내외 AI 기사) |
| 배포 | Vercel 서버리스 |
| 자동 수집 | Vercel Cron 2개: 수집(UTC 22:00/KST 07:00) + 요약(UTC 22:20/KST 07:20) |

---

## 주요 파일 구조

```
Newsletter/
├── api/index.py          ← Vercel 진입점 (from app.main import app)
├── vercel.json           ← Vercel 빌드/라우팅/Cron 설정
├── app/
│   ├── main.py           ← FastAPI 라우터 (/api/cron/collect, /api/cron/summarize 등)
│   ├── models.py         ← SQLAlchemy 모델 (Article)
│   ├── database.py       ← SQLite 연결 (로컬 fallback용, 실서버는 Supabase)
│   ├── supabase_db.py    ← Supabase httpx 직접 호출 (supabase-py 대신)
│   ├── crawler.py        ← RSS 수집기 (URL 중복 방지)
│   ├── summarizer.py     ← OpenRouter 연동, 3줄 한국어 요약, 폴백 로직
│   ├── scheduler.py      ← _async_collection_pipeline() (수집+요약 일괄 실행, limit=20)
│   ├── sources.py        ← RSS 소스 목록 + AI 키워드 (활성 10개 / 비활성 5개)
│   ├── templates/        ← base.html, index.html, news.html
│   └── static/           ← style.css, favicon.svg
├── public/static/        ← Vercel CDN 서빙용 정적 파일 (style.css, favicon.svg)
├── Newsletter_AI.html    ← 브라우저 미리보기용 정적 HTML
└── PRD.md                ← 상품 기획 문서
```

> **주의**: CSS/정적 파일 수정 시 `app/static/`과 `public/static/` **양쪽 모두** 업데이트해야 함.
> Vercel이 `/static/*` 요청을 `public/static/`으로 직접 라우팅하므로 `app/static/`만 수정하면 배포에 반영되지 않음.

---

## 개발 이력 요약

### 1차 (2026-03-02): 앱 초기 구축
- 4개 에이전트(PRD, 백엔드, 프론트엔드, QA)로 분업해 전체 앱 구축
- FastAPI + SQLite + APScheduler + Jinja2 UI 완성
- Playwright MCP로 16개 항목 테스트 → 버그 4개 수정 (타이틀 중복, stats 오류, 파비콘, 보안 헤더)

### 2차 (2026-03-03): Vercel 배포 및 DB 마이그레이션
- Vercel 서버리스 환경 한계 발견:
  - SQLite 파일시스템 read-only → Supabase PostgreSQL로 DB 전환
  - supabase-py HTTP/2 오류 → httpx 직접 호출로 교체
  - SUPABASE_ANON_KEY 줄바꿈 문자 버그 수정 (`.strip()`)
- AI 요약 일일 한도 50건 제한 추가

### 3차 (2026-03-05): 핵심 버그 3개 수정 + 기능 개선
- **버그 수정**:
  - `daemon=True` 스레드가 Vercel Lambda 응답 직후 kill되어 수집/요약 미실행 → `await` 직접 호출로 교체
  - 요약 실패 시 `is_summarized=True`로 잘못 마킹 → 성공 시에만 마킹하도록 수정
  - 한도 초과 기사 "영구 무시" 로직 (NULL 마킹) 제거 → 다음 실행에서 재시도
- **APScheduler → Vercel Cron Job 교체** (`/api/cron/collect`, UTC 22:00)
- AI 요약 형식 150~200자 → **3줄 요약**으로 변경
- OpenRouter 모델 목록 정리 (검증된 무료 모델로 교체)

### 5차 (2026-03-07): Morning Brew 스타일 UI 전면 리디자인
- **디자인 컨셉 변경**: 따뜻한 크림/골드 → Morning Brew 스타일 (다크 헤더 + 클린 화이트 + 포레스트 그린)
- **헤더**: 흰색 배경 → 다크(`#111111`) 배경, 로고·nav 흰색 처리, ☀️ → ☕ 아이콘
- **에디션 바 추가**: 헤더 위 그린 스트립에 오늘 날짜 + "국내외 AI 최신 뉴스" 표시
- **브랜드 컬러**: 골드(`#d4820a`) → 포레스트 그린(`#2d6a4f`) 전체 교체
- **폰트**: Playfair Display 세리프 추가 (로고·제목·수치에 적용)
- **배경**: 크림/베이지(`#fdf8f0`) → 클린 라이트 그레이(`#f5f5f3`)
- **푸터**: 흰색 → 다크(헤더와 통일)
- **Newsletter_AI.html** 프리뷰 파일 동일 디자인으로 업데이트

### 4차 (2026-03-07): RSS 소스 정비 + Cron 타임아웃 수정 + UI 버그 수정
- **Vercel Cron 타임아웃 버그 수정** (`scheduler.py`):
  - `summarize_unsummarized_articles()` → `limit=20` 추가
  - 수집(~35초) + 요약(~90초) = 총 ~125초로 maxDuration 300초 내 완료 보장
- **RSS 소스 정비** (`sources.py`):
  - 죽은 소스 5개 비활성화: Anthropic(404), OpenAI Blog(403), Wired AI(404), ZDNet Korea(404), 전자신문(XML 오류)
  - VentureBeat AI URL 교체: `venturebeat.com/category/ai/feed/` → `feeds.feedburner.com/venturebeat/SZYF`
  - 새 소스 3개 추가: Hugging Face Blog, AI News, Ars Technica AI
  - 활성 소스 6개 → **10개** / 당일 수집 102건 확인
- **UI 버그 수정** (`style.css`):
  - `.summary-text`, `.list-item-summary`에서 `-webkit-line-clamp` 제거
  - AI 3줄 요약이 줄바꿈 포함 시 4줄 이상이 되면 잘리는 문제 수정

### 7차 (2026-03-08): Vercel Cron 미작동 원인 분석 및 수정
- **원인**: Hobby 플랜 함수 실행 한도 60초, 기존 단일 파이프라인(수집+요약 ~125초) 초과로 크론 강제 종료
- **vercel.json 수정**: `maxDuration: 300→60`, 크론 2개로 분리
  - `/api/cron/collect` (UTC 22:00): RSS 수집 전용 ~35초
  - `/api/cron/summarize` (UTC 22:20): AI 요약 전용 limit=10, ~45초
- **main.py**: `_verify_cron_secret()` 헬퍼 추출, `/api/cron/summarize` 엔드포인트 신규 추가
- **CLAUDE.md**: `builds` vs `functions` 포맷 분석 결과 영구 기록

### 6차 (2026-03-08): Vercel 배포 수동 복구 + vercel.json 충돌 수정
- **배포 누락 원인 확인**: Morning Brew UI 커밋(19:50~19:51 KST)이 GitHub에 push됐으나 Vercel GitHub 통합이 자동 배포를 트리거하지 않음
- **vercel.json 충돌 수정**: `functions` + `builds` 동시 사용 불가 오류 → `functions` 블록 제거, `maxDuration: 300`을 `builds.config` 내로 이동
- **수동 배포 완료**: `vercel --prod` CLI로 최신 UI 코드 Production 배포
- **GitHub 자동 배포 복구**: vercel.json 수정 후 push → Vercel GitHub 통합 정상 재작동 확인

---

## 현재 상태 (2026-03-08 기준)

| 항목 | 상태 |
|---|---|
| Supabase 연결 | 정상 |
| 전체 기사 수 | 251건 |
| 요약 완료 | 80건 (32%) |
| 미요약 누적 | 171건 — 요약 크론 실행 시 10건씩 자동 처리 |
| 활성 RSS 소스 | 10개 (비활성 5개) |
| Vercel Cron | 수집 `0 22 * * *` / 요약 `20 22 * * *` — 내일 07:00 KST 첫 실행 예정 |

---

## RSS 소스 현황

| 소스 | 상태 | 비고 |
|---|---|---|
| TechCrunch AI | ✅ 활성 | |
| VentureBeat AI | ✅ 활성 | feedburner URL로 교체 |
| The Verge AI | ✅ 활성 | |
| Google AI Blog | ✅ 활성 | |
| MIT Technology Review AI | ✅ 활성 | |
| Hugging Face Blog | ✅ 활성 | 신규 추가 |
| AI News | ✅ 활성 | 신규 추가 |
| Ars Technica AI | ✅ 활성 | 신규 추가 |
| AI타임스 | ✅ 활성 | |
| 한국경제 IT | ✅ 활성 | |
| Anthropic News | ⏸ 비활성 | 404 |
| OpenAI Blog | ⏸ 비활성 | 403 |
| Wired AI | ⏸ 비활성 | 404 |
| ZDNet Korea | ⏸ 비활성 | 404 |
| 전자신문 | ⏸ 비활성 | XML 파싱 오류 |

---

## Vercel 배포 설정 원칙 (절대 변경 금지)

### vercel.json 포맷: `builds` 사용 (`functions` 사용 불가)

이 프로젝트는 반드시 `builds` 포맷을 사용해야 한다. `functions` 포맷으로 전환 시 항상 빌드 오류 발생.

**`functions` 포맷이 실패하는 이유 (실증됨):**
- `api/index.py`가 `from app.main import app` 한 줄만 있는 re-export 구조 → Vercel이 서버리스 함수로 자동 인식 불가
- 모든 요청을 `api/index.py`로 redirect하는 커스텀 `routes` 설정과 충돌
- `@vercel/python` 빌더 없이는 FastAPI ASGI 앱 구조 처리 불가

**오류 메시지 (보면 `functions` 포맷 썼다는 뜻):**
```
The pattern "api/index.py" defined in `functions` doesn't match any Serverless Functions
```

**올바른 구조:**
```json
"builds": [{ "src": "api/index.py", "use": "@vercel/python", "config": {...} }]
```
빌드 시 `WARN! Due to builds existing...` 경고는 무해함 — 무시할 것.

### Vercel 플랜 제한 (Hobby)
- 함수 최대 실행 시간: **60초** (`maxDuration: 300` 설정해도 Hobby에선 60초 적용)
- Cron Job: 하루 1회, 크론 당 60초 제한
- 수집(~35초)과 요약(~45초)을 **반드시 별도 크론**으로 분리해야 함

---

## 미해결 이슈

1. **비활성 소스 URL 재확인** — Anthropic/OpenAI RSS는 향후 공식 지원 시 재활성화 필요

---

## 환경변수 (.env)

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (무료 모델 사용) |
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_ANON_KEY` | Supabase anon key (한 줄로 입력) |
| `DATABASE_URL` | SQLite 경로 (로컬 fallback, 기본 `sqlite:///app.db`) |
