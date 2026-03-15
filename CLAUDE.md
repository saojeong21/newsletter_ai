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
| AI 요약 | OpenRouter 무료 모델 폴백 (gemma-3-27b → llama-3.3-70b → qwen3-80b → nemotron-120b → gemma-3-12b → mistral-small) |
| 뉴스 수집 | feedparser RSS (활성 10개 소스, 국내외 AI 기사) |
| 배포 | Vercel 서버리스 |
| 자동 수집 | GitHub Actions (주): 3시간마다 수집→요약×2 순차 실행 / Vercel Cron (백업) |

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
├── .github/workflows/
│   └── cron.yml          ← GitHub Actions 크론 (3시간마다 수집→요약×2 순차, Vercel 크론 백업)
├── Newsletter_AI.html    ← 브라우저 미리보기용 정적 HTML
└── PRD.md                ← 상품 기획 문서
```

> **주의**: CSS/정적 파일 수정 시 `app/static/`과 `public/static/` **양쪽 모두** 업데이트해야 함.
> Vercel이 `/static/*` 요청을 `public/static/`으로 직접 라우팅하므로 `app/static/`만 수정하면 배포에 반영되지 않음.

---

## 개발 이력 (압축)

- **1차 (03-02)**: FastAPI+SQLite+APScheduler+Jinja2 초기 구축, 버그 4개 수정
- **2차 (03-03)**: Vercel 배포. SQLite→Supabase, supabase-py→httpx 직접 호출
- **3차 (03-05)**: daemon 스레드→await 교체, 요약 마킹 버그 수정, APScheduler→Vercel Cron, 3줄 요약 형식
- **4차 (03-07)**: RSS 소스 정비 (활성 6→10개), Cron timeout 수정, 3줄 요약 클램프 버그 수정
- **5차 (03-07)**: Morning Brew 스타일 UI 리디자인 (다크헤더+포레스트그린, Playfair Display)
- **6차 (03-08)**: vercel.json `functions`+`builds` 충돌 수정, 수동 배포 복구
- **7차 (03-08)**: Cron 2개 분리 (수집 22:00 / 요약 22:20), limit=10으로 60초 내 완료
- **8차 (03-10)**: 4가지 버그 수정
  - `Ars Technica AI` → `AI_NATIVE_SOURCES` 누락 수정 (3/7 이후 수집 0건 원인)
  - Google AI Blog URL 301 리다이렉트 최종 URL로 교체
  - 요약 cron `limit=10→5` (90초→52초, 60초 제한 내)
  - 요약 모델 4개→6개, 공급사 2→4개 분산 (동시 rate limit 방지)
- **9차 (03-11)**: Supabase 보안 강화
  - `ainewsletter_items` 테이블 RLS 활성화
  - SELECT: anon/authenticated 허용, INSERT/UPDATE/DELETE: service_role만 허용
  - `supabase_db.py` 쓰기 함수(`save_article`, `update_summary`)에 `_service_headers()` 적용
  - 환경변수 `SUPABASE_SERVICE_ROLE_KEY` 추가 (Vercel + 로컬 .env)
- **10차 (03-12)**: GitHub Actions 크론 추가 (Vercel Hobby 크론 불안정 대응)
  - `.github/workflows/cron.yml` 추가 — UTC 22:00 수집→요약 순차 실행 (`needs: collect`)
  - Vercel Deployment Protection 우회: `x-vercel-protection-bypass` 헤더 적용
  - GitHub Secrets: `CRON_SECRET`, `VERCEL_BYPASS_SECRET` 등록
  - Vercel Cron은 백업으로 유지
- **11차 (03-14)**: OpenRouter 요약 모델 교체 (rate limit 내성 강화)
  - `nousresearch/hermes-3-llama-3.1-405b` → `nvidia/nemotron-3-super-120b-a12b` (NVIDIA 공급사 추가)
  - `openai/gpt-oss-20b` 제거 — OpenRouter 계정 프라이버시 설정 필요한 모델 (404 오류)
  - 최종 공급사 구성: Google · Meta · Alibaba · NVIDIA · Mistral (5개)
- **12차 (03-16)**: 크론 스케줄 및 요약 처리량 개선
  - GitHub Actions 스케줄 `0 22 * * *` → `0 */3 * * *` (하루 1회→3시간마다, 8회/일)
  - 요약 job 2회 순차 실행 추가 (`summarize` → `summarize2`, `needs` 체인)
  - 처리량: 5건/실행 → 10건/실행, 40건/일 → 80건/일 (백로그 142건 약 2일 내 해소 예상)
  - Vercel Cron: Hobby 플랜 하루 1회 제한으로 변경 불가 — 일 1회 백업 유지

---

## 현재 상태 (2026-03-16 기준)

| 항목 | 상태 |
|---|---|
| Supabase 연결 | 정상 |
| 전체 기사 수 | ~527건 |
| 요약 완료 | 385건 완료 / 미요약 142건 (80건/일 처리, 약 2일 내 해소 예상) |
| 활성 RSS 소스 | 10개 (비활성 5개) |
| GitHub Actions 크론 | `0 */3 * * *` 수집→요약×2 순차 — 정상 작동 확인 |
| Vercel Cron | 수집 `0 22 * * *` / 요약 `20 22 * * *` — 백업 유지 |
| 요약 모델 | 6개 / 5개 공급사 분산 (Google·Meta·Alibaba·NVIDIA·Mistral) |

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
| `SUPABASE_ANON_KEY` | Supabase anon key (읽기 전용, 한 줄로 입력) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (쓰기 전용 — RLS 우회) |
| `DATABASE_URL` | SQLite 경로 (로컬 fallback, 기본 `sqlite:///app.db`) |
| `CRON_SECRET` | Vercel/GitHub Actions 크론 인증 시크릿 (Authorization: Bearer) |
| `VERCEL_BYPASS_SECRET` | Vercel Deployment Protection 우회 토큰 (GitHub Actions용, GitHub Secrets에 저장) |
