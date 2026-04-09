# CLAUDE.md

## 프로젝트

**Newsletter AI** — 매일 아침 국내외 주요 AI 관련 뉴스를 자동으로 수집해서 보여주는 웹 애플리케이션.

배포 URL: `https://newsletter-ai-saojeong21s-projects.vercel.app`
GitHub: `https://github.com/saojeong21/newsletter_ai`

---

## 기술 스택

| 항목 | 내용 |
|---|---|
| 백엔드 | FastAPI + Jinja2 (SSR) |
| DB | Supabase PostgreSQL (`ainewsletter_items` 테이블) |
| 뉴스 수집 | feedparser RSS (활성 10개 소스, 국내외 AI 기사) |
| AI 요약 | Obsidian 스크랩 시에만 OpenRouter 무료 모델 폴백 (obsidian_agent.py) |
| 배포 | Vercel 서버리스 |
| 자동 수집 | GitHub Actions (주): 3시간마다 수집 / Vercel Cron (백업) |

---

## 주요 파일 구조

```
Newsletter/
├── api/index.py          ← Vercel 진입점 (from app.main import app)
├── vercel.json           ← Vercel 빌드/라우팅/Cron 설정
├── app/
│   ├── main.py           ← FastAPI 라우터 (/api/cron/collect 등)
│   ├── models.py         ← SQLAlchemy 모델 (Article)
│   ├── database.py       ← SQLite 연결 (로컬 fallback용, 실서버는 Supabase)
│   ├── supabase_db.py    ← Supabase httpx 직접 호출 (supabase-py 대신)
│   ├── crawler.py        ← RSS 수집기 (URL 중복 방지)
│   ├── scheduler.py      ← _async_collection_pipeline() (수집 전용)
│   ├── sources.py        ← RSS 소스 목록 + AI 키워드 (활성 10개 / 비활성 5개)
│   ├── templates/        ← base.html, index.html, news.html
│   └── static/           ← style.css, favicon.svg
├── public/static/        ← Vercel CDN 서빙용 정적 파일 (style.css, favicon.svg)
├── .github/workflows/
│   └── cron.yml          ← GitHub Actions 크론 (3시간마다 수집, Vercel 크론 백업)
├── Newsletter_AI.html    ← 브라우저 미리보기용 정적 HTML
└── PRD.md                ← 상품 기획 문서
```

> **주의**: CSS/정적 파일 수정 시 `app/static/`과 `public/static/` **양쪽 모두** 업데이트해야 함.
> Vercel이 `/static/*` 요청을 `public/static/`으로 직접 라우팅하므로 `app/static/`만 수정하면 배포에 반영되지 않음.

---

## 개발 이력 (압축)

- **1~7차 (03-02~03-08)**: 초기 구축 → Vercel+Supabase 배포 → Cron 분리, 소스 10개, 버그 수정
- **8차 (03-10)**: Ars Technica 누락 수정, 요약 모델 6개·공급사 4개로 분산
- **9차 (03-11)**: Supabase RLS 활성화, service_role key로 쓰기 권한 분리
- **10차 (03-12)**: GitHub Actions 3시간 크론 추가, Vercel Protection 우회
- **11~12차 (03-14~03-16)**: 모델 교체(NVIDIA→DeepSeek), 크론 8회/일·요약 80건/일로 개선
- **13차 (03-17)**: 아키텍처 검토 — 모델 ID 수정, 프롬프트 강화, HTML \n→br 버그, limit DB 직달, asyncio 수정, AI_KEYWORDS 보강
- **14차 (03-17)**: UI 전면 리디자인 — 모던 카드 레이아웃
  - Morning Brew 다크 테마 → 라벤더-화이트 배경 (`#f5f4ff`) 클린 카드 UI로 교체
  - 폰트: Playfair Display + Inter → **DM Sans + Noto Sans KR**
  - 히어로: 그라디언트 타이틀, 통계 뱃지, 날짜 선택기 + 수집 버튼 한 줄 배치
  - 소스 카드 스트립: 소스별 앱 아이콘 스타일 컬러 뱃지 + 기사 수 표시
  - 뉴스 카드: 3열 그리드, 소스 컬러 아이콘, 검색+지역 필터 바
  - `public/static/style.css` 동시 업데이트 (Vercel CDN 반영)
- **15차 (03-17)**: 요약 언어 소스별 자동 분리
  - 국내 소스(AI타임스, 한국경제 IT) → 한국어 3줄 요약
  - 해외 소스(TechCrunch, VentureBeat 등) → 영어 3문장 요약
  - `_is_korean_source()` 판별 함수 + `SUMMARY_PROMPT_EN` 템플릿 추가
  - 기존 요약 완료 기사는 재처리 없음 (신규 기사부터 적용)
- **16차 (04-01)**: Obsidian 저널 스크랩 기능 (완료)
  - 기사 카드에 🔖 스크랩 버튼 추가 — 클릭 시 원문 크롤링 후 로컬 Obsidian에 저장
  - `obsidian_agent.py` 로컬 데몬: trafilatura 크롤링 → `~/Documents/Obsidian/02-Areas/Journal/YYYY-MM-DD.md` append (날짜별 단일 파일, `---` 구분)
  - LaunchAgent 등록 (`~/Library/LaunchAgents/com.newsletter.obsidian-agent.plist`) — 로그인 시 자동 시작, `--ssl` 모드로 상시 실행
  - mkcert SSL (`~/.mkcert/192.168.0.10+1.pem`) — HTTPS 지원
  - 실행: `pip install flask flask-cors trafilatura lxml_html_clean` (최초 1회, 이후 LaunchAgent 자동 실행)
  - **18차에서 변경**: 브라우저 직접 호출 제거 → Supabase 큐 폴링 방식으로 전환
- **17차 (04-04)**: AI 요약을 뉴스레터 파이프라인에서 제거, Obsidian 스크랩 전용으로 이전
  - `app/summarizer.py` 삭제, `/api/summarize` · `/api/cron/summarize` 엔드포인트 제거
  - GitHub Actions cron에서 summarize 잡 2개 제거, Vercel Cron에서 summarize 스케줄 제거
  - 수집 파이프라인은 RSS 수집만 수행, AI 요약은 Obsidian 스크랩 시에만 실행
- **18차 (04-06)**: 스크랩 상태 기기 간 동기화 + 오프라인 큐
  - 스크랩 상태를 `ainewsletter_items.is_scrapped` (Supabase)에 저장 → 웹/아이폰/아이패드 동기화
  - `scrap_queue` 테이블 신규 생성 — MacBook 잠자기 중 스크랩 요청을 큐에 저장
  - 브라우저 → obsidian_agent 직접 호출 제거, `POST /api/scrap` (Vercel) 경유로 변경
  - `GET /api/scrap/pending` · `POST /api/scrap/done` 엔드포인트 추가 (에이전트용, CRON_SECRET 인증)
  - `obsidian_agent.py` — 60초 간격 Supabase 큐 폴링 백그라운드 스레드 추가 (재시작 시 즉시 처리)
  - 프론트엔드: 에이전트 URL 설정 UI 제거, 서버 렌더링으로 is_scrapped 상태 표시
- **19차 (04-09)**: obsidian_agent 버그 수정 2건
  - `logging.basicConfig()` 추가 — 큐 폴링 스레드 상태가 로그에 기록되지 않던 문제 수정
  - 스크랩 날짜 기준 파일 분리 — `_write_to_obsidian()`이 처리 시각(`now()`) 대신 `created_at`(KST 변환) 기준으로 날짜 파일 결정하도록 수정
  - **운영 주의**: `obsidian_agent.py` 수정 후 반드시 LaunchAgent 재시작 필요 (`launchctl unload/load`)

---

## 현재 상태 (2026-04-09 기준)

| 항목 | 상태 |
|---|---|
| Supabase 연결 | 정상 |
| 활성 RSS 소스 | 10개 (비활성 5개) |
| GitHub Actions 크론 | `0 */3 * * *` 수집 전용 — 정상 작동 |
| Vercel Cron | 수집 `0 22 * * *` — 백업 유지 |
| AI 요약 | 뉴스레터 파이프라인에서 제거 (17차~), Obsidian 스크랩 시에만 실행 |
| Obsidian 스크랩 | Supabase 큐 경유 (18차~) — 기기 간 동기화, MacBook 잠자기 중 큐 보관 후 처리 |
| 스크랩 상태 동기화 | `ainewsletter_items.is_scrapped` — 웹/아이폰/아이패드 실시간 동기화 |

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
- 수집 크론만 사용 (AI 요약은 17차에서 파이프라인에서 제거됨)

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
