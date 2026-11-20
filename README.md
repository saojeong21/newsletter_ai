# AI 뉴스레터

매일 아침 국내외 주요 AI 뉴스를 자동 수집하고 한국어로 요약해서 보여주는 웹 애플리케이션.

## 주요 기능

- **뉴스 자동 수집**: 매일 오전 7시(KST) RSS 피드에서 AI 관련 기사 수집
- **AI 한국어 요약**: OpenRouter API(무료 모델)로 각 기사를 한국어로 요약
- **웹 UI**: 카드 형태로 오늘의 뉴스 표시, 날짜별 아카이브, 국내/해외 필터
- **모닝 브리핑**: `/briefing` — AI·주식 / 국내 부동산 / 삼프로TV·경제방송 / 링크드인 AI 피드 4개 섹션, 날짜별 JSON 기반
- **중복 방지**: URL 기준으로 이미 수집된 기사는 재수집하지 않음
- **트렌드 키워드**: 수집 기사 제목 기반 실시간 키워드 분석

## 뉴스 소스

| 소스 | 카테고리 |
|---|---|
| TechCrunch AI | 해외 AI |
| VentureBeat AI | 해외 AI |
| The Verge AI | 해외 AI |
| Google AI Blog | 해외 AI |
| Anthropic News | 해외 AI |
| OpenAI Blog | 해외 AI |
| MIT Technology Review | 해외 AI |
| Wired AI | 해외 AI |
| ZDNet Korea | 국내 IT |
| 전자신문 | 국내 IT |
| AI타임스 | 국내 AI |
| 한국경제 IT | 국내 IT |

## 기술 스택

- **백엔드**: Python, FastAPI, SQLAlchemy, APScheduler
- **프론트엔드**: Jinja2 템플릿, CSS (반응형)
- **DB**: SQLite
- **AI**: OpenRouter API (무료 모델 폴백)
- **RSS 파싱**: feedparser

## 시작하기

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 OPENROUTER_API_KEY 입력
```

### 3. 서버 실행

```bash
uvicorn app.main:app --reload
```

서버가 실행되면 `http://localhost:8000` 에서 확인할 수 있습니다.

### 4. 뉴스 즉시 수집

```bash
curl -X POST http://localhost:8000/api/collect
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 오늘의 뉴스 홈 화면 |
| GET | `/?date=YYYY-MM-DD` | 날짜별 뉴스 |
| GET | `/news` | 뉴스 아카이브 |
| GET | `/briefing` | 모닝 브리핑 (최신 날짜) |
| GET | `/briefing?date=YYYY-MM-DD` | 날짜별 모닝 브리핑 |
| POST | `/api/collect` | 즉시 수집 트리거 |
| GET | `/api/articles` | 기사 목록 JSON |
| GET | `/api/stats` | 수집 통계 |
| GET | `/health` | 서버 상태 |

## 모닝 브리핑 데이터 넣기

`/briefing` 은 저장소의 `data/briefings/YYYY-MM-DD.json` 을 읽어 렌더링합니다. 뉴스 수집 파이프라인과 분리되어 있어, 매일 아침 브리핑 JSON을 커밋·푸시하면 Vercel 자동 배포로 바로 반영됩니다.

```json
{
  "date": "2026-11-20",
  "headline": "한 줄 요약",
  "coverage": "수집 범위",
  "notes": ["안내 문구"],
  "sections": [
    {
      "key": "ai_stock",
      "title": "AI·주식",
      "lead": "섹션 요약",
      "items": [
        { "title": "...", "url": "https://...", "source_name": "한국경제",
          "published_at": "2026-11-20T07:06", "summary": "...",
          "tags": ["미국증시"], "highlight": true }
      ]
    }
  ]
}
```

- `sections[].key` 는 `ai_stock`, `realestate`, `broadcast`, `linkedin` 4개를 사용합니다.
- 링크드인 글은 `author`(작성자·소속)와 `posted_label`(피드 표시값, 예 `1h`)을 추가로 넣을 수 있습니다.
- 각 카드의 🔖 스크랩 버튼은 기존 `/api/scrap` 을 호출합니다.
- 회귀 테스트: `python -m pytest tests -q` (Supabase는 stub 처리)

## 환경변수

| 변수 | 설명 | 필수 |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API 키 | 필수 |
| `DATABASE_URL` | SQLite DB 경로 (기본: `sqlite:///app.db`) | 선택 |
| `LOG_LEVEL` | 로그 레벨 (기본: `INFO`) | 선택 |
