# AI 뉴스레터 웹 애플리케이션 PRD

**문서 버전**: 1.0
**작성일**: 2026-03-02
**작성자**: Product Planning Manager
**상태**: 초안 (Draft)

---

## 1. 개요 (Overview)

### 1.1 제품 비전

> "매일 아침, 바쁜 AI 종사자와 관심자가 전 세계 주요 AI 뉴스를 5분 안에 파악할 수 있도록 한다."

### 1.2 배경 및 문제 정의

AI 산업이 빠르게 성장하면서 국내외 주요 기업들의 동향 파악이 중요해졌다. 그러나 현재:

- 해외 테크 미디어(TechCrunch, VentureBeat 등)와 국내 IT 언론(ZDNet Korea, AI타임스 등)을 **각각 개별적으로 방문**해야 하는 번거로움이 존재한다.
- 영문 기사를 빠르게 소화하기 어렵고, **한국어 요약이 제공되지 않는다**.
- 여러 소스에서 중복 기사가 반복 노출되어 **정보 피로도(Information Fatigue)** 가 높다.
- 관심 기업(Nvidia, 삼성, 네이버 등)의 뉴스를 한 곳에서 필터링하기 어렵다.

이 제품은 RSS 피드 자동 수집과 AI 요약 기술을 결합하여, 위 문제를 해소하는 **단일 AI 뉴스 허브**를 제공한다.

### 1.3 목표 (Objectives & Key Results)

| 목표 (Objective) | 핵심 결과 (Key Result) | 측정 기준 |
|---|---|---|
| 신뢰할 수 있는 뉴스 자동 수집 | 매일 오전 7시 기준 수집 성공률 95% 이상 | APScheduler 실행 로그 |
| 사용자 편의성 향상 | 기사 한국어 요약 제공률 100% | DB 내 요약 컬럼 null 비율 |
| 중복 콘텐츠 최소화 | URL 기준 중복 수집률 0% | DB unique URL 검증 |
| 빠른 콘텐츠 탐색 | 홈 페이지 로딩 2초 이내 (p95) | 서버 응답 시간 측정 |

---

## 2. 대상 사용자 (Target Users)

### 2.1 사용자 페르소나

#### 페르소나 A — "AI 업계 종사자 김지훈 (32세)"
- **직군**: 국내 AI 스타트업 ML 엔지니어
- **목표**: 매일 출근 전 30분 안에 경쟁사 및 글로벌 AI 트렌드 파악
- **불편함**: 영문 기사를 읽는 데 시간이 오래 걸리고, 여러 뉴스 사이트를 순회해야 함
- **활용 방식**: 매일 오전 7~8시 스마트폰/노트북으로 접속, 카드뷰 훑어보기

#### 페르소나 B — "비즈니스 의사결정자 이수연 (45세)"
- **직군**: 대기업 디지털 전환 담당 임원
- **목표**: 국내외 빅테크 및 AI 기업 동향을 빠르게 보고서에 인용
- **불편함**: 기술 용어가 많고 핵심 요점이 어디 있는지 파악하기 어려움
- **활용 방식**: 이메일 알림 또는 북마크로 접속, 한국어 요약 위주로 소비

#### 페르소나 C — "AI 관심 학생 박민준 (24세)"
- **직군**: 대학원생 (AI 전공)
- **목표**: 최신 AI 기술 동향과 주요 기업 발표 추적
- **불편함**: 무료로 접근 가능한 통합 뉴스 채널이 없음
- **활용 방식**: 날짜별 아카이브 탐색, 특정 기업 뉴스 필터링

### 2.2 사용자 여정 (User Journey)

```
[오전 7시 이전] 스케줄러 자동 실행
      |
      v
[뉴스 수집] RSS 피드에서 최신 기사 수집
      |
      v
[AI 요약] OpenRouter API로 한국어 요약 생성
      |
      v
[DB 저장] SQLite에 기사 + 요약 저장
      |
      v
[오전 7~9시] 사용자가 웹 UI 접속
      |
      v
[홈 화면] 오늘의 AI 뉴스 카드뷰 확인
      |
      v
[날짜 필터] 과거 날짜 아카이브 탐색
      |
      v
[기사 클릭] 원문 링크로 이동 (새 탭)
```

---

## 3. 기능 요구사항 (Functional Requirements)

### 3.1 기능 우선순위 (MoSCoW)

| 우선순위 | 기능 |
|---|---|
| **Must-have** | RSS 피드 자동 수집 |
| **Must-have** | AI 한국어 요약 생성 |
| **Must-have** | SQLite DB 저장 및 중복 방지 |
| **Must-have** | 웹 UI 카드뷰 (오늘의 뉴스) |
| **Must-have** | 날짜별 필터링 |
| **Should-have** | 수동 수집 트리거 (관리자용 API) |
| **Should-have** | 기사 원문 링크 연결 |
| **Should-have** | 뉴스 소스별 태그/뱃지 표시 |
| **Could-have** | 기업별 필터링 |
| **Could-have** | 키워드 검색 기능 |
| **Won't-have (v1)** | 사용자 로그인 및 개인화 |
| **Won't-have (v1)** | 이메일 뉴스레터 발송 |
| **Won't-have (v1)** | 댓글 및 소셜 공유 |

### 3.2 기능별 상세 명세

---

#### F-01: RSS 피드 자동 수집

**설명**: APScheduler를 이용하여 매일 오전 7시에 지정된 RSS 피드 목록에서 최신 기사를 수집한다.

**사용자 스토리**:
> As a 시스템 스케줄러,
> I want to 매일 오전 7시에 RSS 피드에서 기사를 자동 수집하고,
> So that 사용자가 최신 AI 뉴스를 아침에 확인할 수 있다.

**상세 동작**:
- 수집 대상: 섹션 8의 RSS 소스 목록 전체
- 수집 항목: 기사 제목(title), 원문 URL(link), 발행일시(pub_date), 기사 본문 또는 요약(description), 출처(source_name)
- 중복 처리: URL 기준으로 이미 DB에 존재하는 기사는 건너뜀
- 오류 처리: 특정 피드 수집 실패 시 해당 피드만 스킵하고 나머지 계속 진행, 오류는 로그에 기록

**인수 기준 (Acceptance Criteria)**:
- [ ] 스케줄러가 매일 오전 7시(KST)에 자동 실행됨
- [ ] 각 RSS 피드에서 최신 기사 최대 20건을 수집함
- [ ] 수집된 기사가 DB에 정상 저장됨
- [ ] 동일 URL의 기사는 DB에 중복 저장되지 않음
- [ ] 피드 수집 실패 시 로그에 오류가 기록되고 나머지 피드는 계속 처리됨

---

#### F-02: AI 한국어 요약 생성

**설명**: OpenRouter API의 무료 LLM 모델을 활용하여 수집된 각 기사를 한국어로 3~5문장으로 요약한다.

**사용자 스토리**:
> As a 사용자,
> I want to 영문 기사를 한국어로 요약한 내용을 보고 싶고,
> So that 영어 독해 없이도 핵심 내용을 빠르게 파악할 수 있다.

**상세 동작**:
- 요약 대상: 새로 수집된 기사 중 요약이 없는 기사
- 사용 모델: `google/gemini-2.0-flash-exp:free` (무료 모델 우선, 실패 시 `meta-llama/llama-3.3-70b-instruct:free` 폴백)
- 요약 프롬프트:
  ```
  다음 기사를 한국어로 3~5문장으로 핵심 내용만 요약해줘.
  불필요한 서론 없이 바로 요약 내용만 작성해.

  제목: {title}
  내용: {content}
  ```
- 요약 길이: 150~300자 (한국어 기준)
- API 실패 시: 재시도 1회, 이후에도 실패 시 `summary` 필드를 빈 값으로 두고 저장
- Rate Limit 대응: 기사 간 1초 딜레이 적용

**인수 기준**:
- [ ] 수집된 모든 기사에 대해 한국어 요약이 생성됨
- [ ] 요약 텍스트가 150자 이상 300자 이하임
- [ ] API 오류 발생 시 오류 로그가 남고 기사는 요약 없이 저장됨
- [ ] 요약 생성 시 원문 제목과 내용을 모두 활용함

---

#### F-03: SQLite DB 저장 및 중복 방지

**설명**: 수집된 기사와 AI 요약을 SQLite DB에 영구 저장하며, URL 기준으로 중복을 방지한다.

**사용자 스토리**:
> As a 시스템,
> I want to 수집된 기사를 DB에 안정적으로 저장하고,
> So that 웹 UI가 DB에서 빠르게 기사를 조회할 수 있다.

**상세 동작**:
- ORM: SQLAlchemy 사용
- 중복 체크: INSERT 전 URL로 SELECT 조회, 존재하면 건너뜀 (또는 `INSERT OR IGNORE`)
- 저장 성공 시 로그에 저장된 기사 수 기록

**인수 기준**:
- [ ] 기사가 DB에 정상 저장됨
- [ ] 동일 URL 기사는 DB에 1건만 존재함
- [ ] DB 파일이 지정된 경로(`DATABASE_URL`)에 생성됨
- [ ] DB 스키마가 애플리케이션 시작 시 자동 생성됨 (없을 경우)

---

#### F-04: 웹 UI — 오늘의 뉴스 카드뷰

**설명**: FastAPI + Jinja2로 오늘 수집된 뉴스를 카드 형태로 표시한다.

**사용자 스토리**:
> As a 사용자,
> I want to 오늘 수집된 AI 뉴스를 카드 형태로 한눈에 보고 싶고,
> So that 중요한 뉴스를 빠르게 훑어볼 수 있다.

**카드 UI 구성 요소**:
- 기사 제목 (한국어 또는 원문)
- 출처 뱃지 (예: TechCrunch, ZDNet Korea)
- 발행일시
- AI 요약 텍스트 (한국어, 최대 3줄 미리보기)
- "원문 보기" 링크 버튼 (새 탭 열기)

**레이아웃**:
- 반응형 그리드 (모바일: 1열, 태블릿: 2열, 데스크탑: 3열)
- 최신 기사 순서로 정렬

**인수 기준**:
- [ ] 홈 화면(`/`)에서 오늘 날짜의 기사가 표시됨
- [ ] 기사가 없을 경우 "오늘 수집된 뉴스가 없습니다" 메시지 표시
- [ ] 각 카드에 제목, 출처, 발행일시, AI 요약, 원문 링크가 표시됨
- [ ] 원문 링크 클릭 시 새 탭에서 열림
- [ ] 모바일 화면(375px 이상)에서 레이아웃이 깨지지 않음

---

#### F-05: 날짜별 필터링

**설명**: 날짜 선택기(Date Picker)로 과거 날짜의 뉴스 아카이브를 탐색할 수 있다.

**사용자 스토리**:
> As a 사용자,
> I want to 특정 날짜의 뉴스를 다시 보고 싶고,
> So that 과거의 AI 뉴스 동향을 참고할 수 있다.

**상세 동작**:
- URL 파라미터 방식: `/?date=2026-03-01`
- 날짜 선택 시 해당 날짜에 수집된 기사 목록 표시
- 뉴스가 없는 날짜 선택 시 안내 메시지 표시

**인수 기준**:
- [ ] 홈 화면에 날짜 선택기가 표시됨
- [ ] 날짜 변경 시 해당 날짜의 기사 목록이 표시됨
- [ ] URL에 `?date=YYYY-MM-DD` 형식으로 날짜가 반영됨
- [ ] 미래 날짜 선택 시 "해당 날짜의 뉴스가 없습니다" 표시

---

#### F-06: 수동 수집 트리거 (Should-have)

**설명**: 관리자가 스케줄을 기다리지 않고 즉시 뉴스 수집을 실행할 수 있는 API 엔드포인트를 제공한다.

**사용자 스토리**:
> As a 관리자,
> I want to API를 호출하여 즉시 뉴스 수집을 실행하고 싶고,
> So that 스케줄 시간 외에도 최신 뉴스를 즉시 수집할 수 있다.

**인수 기준**:
- [ ] `POST /api/collect` 호출 시 뉴스 수집이 즉시 실행됨
- [ ] 응답으로 수집된 기사 수와 처리 시간이 반환됨
- [ ] 이미 수집 중일 경우 409 응답 반환

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

### 4.1 성능 요구사항

| 항목 | 요구사항 |
|---|---|
| 홈 페이지 응답 시간 | 95th percentile 기준 2초 이내 |
| DB 기사 조회 응답 시간 | 100ms 이내 (인덱스 적용 기준) |
| 뉴스 수집 1회 소요 시간 | 전체 피드 기준 10분 이내 완료 |
| AI 요약 생성 속도 | 기사당 평균 5초 이내 (API 응답 기준) |
| 동시 접속 사용자 | MVP 단계에서 10명 이하 (단일 서버 기준) |

### 4.2 보안 요구사항

| 항목 | 요구사항 |
|---|---|
| API 키 관리 | `.env` 파일로 관리, 코드에 하드코딩 금지 |
| `.env` 파일 | `.gitignore` 에 포함, 절대 버전 관리에 포함하지 않음 |
| 관리자 API | MVP 단계에서는 localhost 접근만 허용 |
| 의존성 취약점 | 정기적으로 `pip audit` 또는 `safety` 로 점검 |
| SQL Injection | SQLAlchemy ORM 사용으로 직접 쿼리 방지 |

### 4.3 가용성 및 신뢰성

| 항목 | 요구사항 |
|---|---|
| 스케줄러 안정성 | 서버 재시작 후에도 스케줄이 자동 복구됨 |
| RSS 피드 장애 대응 | 특정 피드 실패 시 나머지 피드 수집 계속 진행 |
| API 장애 대응 | OpenRouter API 실패 시 요약 없이 기사 저장 후 진행 |
| 로그 | 수집 성공/실패, 요약 성공/실패를 structured logging으로 기록 |

### 4.4 확장성

| 항목 | 현재 MVP | 향후 고려 |
|---|---|---|
| DB | SQLite (단일 파일) | PostgreSQL 마이그레이션 가능하도록 SQLAlchemy 추상화 |
| 배포 | 로컬 실행 또는 단일 서버 | Docker 컨테이너화 고려 |
| 뉴스 소스 | 9개 RSS 피드 | 설정 파일(`sources.json`)로 소스 추가/삭제 가능하도록 설계 |
| AI 요약 모델 | 무료 모델 우선 | 모델명을 환경변수로 교체 가능하도록 설계 |

---

## 5. 범위 외 항목 (Out of Scope — v1)

다음 기능은 v1에서 구현하지 않는다. 사용자 피드백 수집 후 v2에서 우선순위를 재평가한다.

- 사용자 회원가입 / 로그인 / 개인화
- 이메일 뉴스레터 자동 발송
- 푸시 알림
- 댓글, 좋아요, 소셜 공유
- 기업별 필터링 (v1에서는 전체 기사만 표시)
- 키워드 검색
- 기사 원문 전체 크롤링 (RSS 제공 내용만 사용)
- 관리자 대시보드 UI
- 다국어 UI (한국어만 지원)
- 유료 구독 모델

---

## 6. 의존성 및 제약사항 (Dependencies & Constraints)

### 6.1 외부 의존성

| 의존성 | 용도 | 위험도 |
|---|---|---|
| OpenRouter API | AI 요약 생성 | 중간 (무료 모델 rate limit 가능성) |
| RSS 피드 제공 언론사 | 뉴스 수집 | 낮음 (피드 URL 변경 가능성 있음) |

### 6.2 기술 제약사항

- Python 3.10 이상 환경 필요
- SQLite는 단일 Write 스레드 제한 (동시 수집 방지로 해결)
- OpenRouter 무료 모델은 rate limit이 존재하므로 요약 요청 간 딜레이 필요
- The Verge 등 일부 피드는 전체 본문을 제공하지 않을 수 있음 (요약 품질 영향 가능)

### 6.3 환경변수

| 변수명 | 설명 | 필수 여부 |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API 인증 키 | 필수 |
| `DATABASE_URL` | SQLite DB 파일 경로 (예: `sqlite:///app.db`) | 필수 |
| `SCHEDULER_HOUR` | 자동 수집 실행 시각 (기본값: 7) | 선택 |
| `OPENROUTER_MODEL` | 사용할 LLM 모델 ID (기본값: `google/gemini-2.0-flash-exp:free`) | 선택 |
| `LOG_LEVEL` | 로그 레벨 (기본값: `INFO`) | 선택 |

---

## 7. 기술 아키텍처 개요 (Technical Architecture)

### 7.1 시스템 구성도

```
┌──────────────────────────────────────────────────────────┐
│                      외부 서비스                          │
│  RSS 피드 (TechCrunch, VentureBeat 등)  OpenRouter API   │
└───────────────┬──────────────────────────────┬───────────┘
                │ HTTP GET                     │ HTTP POST
                v                              v
┌──────────────────────────────────────────────────────────┐
│                   Python 애플리케이션                     │
│                                                          │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐   │
│  │ APScheduler │──>│ RSS Fetcher │──>│ AI Summarizer │  │
│  │ (매일 07:00) │   │ (feedparser) │  │ (OpenRouter)  │  │
│  └─────────────┘   └──────┬──────┘   └──────┬───────┘   │
│                            │                 │           │
│                            v                 v           │
│                     ┌──────────────────────────────┐     │
│                     │       SQLite DB              │     │
│                     │    (SQLAlchemy ORM)          │     │
│                     └──────────────┬───────────────┘     │
│                                    │                     │
│  ┌───────────────────────────────  │  ───────────────┐   │
│  │          FastAPI 서버           │                  │   │
│  │  ┌──────────────┐  ┌───────────v──────────────┐   │   │
│  │  │  REST API    │  │   Jinja2 템플릿 렌더링    │   │   │
│  │  │ /api/collect │  │   / (홈), /?date=...      │   │   │
│  │  └──────────────┘  └──────────────────────────┘   │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────┘
                               │
                               v
                    ┌──────────────────┐
                    │    웹 브라우저    │
                    │  (사용자 접속)    │
                    └──────────────────┘
```

### 7.2 기술 스택

| 레이어 | 기술 | 버전 |
|---|---|---|
| 웹 프레임워크 | FastAPI | 0.115.x |
| 템플릿 엔진 | Jinja2 | 3.x |
| WSGI/ASGI 서버 | Uvicorn | 0.32.x |
| ORM | SQLAlchemy | 2.x |
| DB | SQLite | 3.x (내장) |
| RSS 파싱 | feedparser | 6.x |
| HTTP 클라이언트 | httpx | 0.27.x |
| 스케줄러 | APScheduler | 3.x |
| 환경변수 | python-dotenv | 1.x |
| 로깅 | Python 표준 logging | — |

### 7.3 프로젝트 디렉토리 구조

```
Newsletter/
├── .env                    # 환경변수 (gitignore)
├── .env.example            # 환경변수 템플릿
├── .gitignore
├── CLAUDE.md
├── PRD.md
├── requirements.txt        # Python 의존성
├── main.py                 # FastAPI 앱 진입점 + APScheduler 초기화
├── app/
│   ├── __init__.py
│   ├── database.py         # SQLAlchemy 엔진 및 세션 설정
│   ├── models.py           # DB 모델 (Article)
│   ├── fetcher.py          # RSS 피드 수집 로직
│   ├── summarizer.py       # OpenRouter AI 요약 로직
│   ├── scheduler.py        # APScheduler 작업 정의
│   ├── sources.py          # RSS 피드 소스 목록
│   └── routers/
│       ├── web.py          # 웹 UI 라우터 (Jinja2 렌더링)
│       └── api.py          # REST API 라우터
├── templates/
│   ├── base.html           # 공통 레이아웃
│   ├── index.html          # 홈 (뉴스 카드뷰)
│   └── components/
│       └── card.html       # 기사 카드 컴포넌트
└── static/
    └── style.css           # 최소한의 CSS 스타일
```

---

## 8. 데이터 모델 (Data Model)

### 8.1 Articles 테이블

| 컬럼명 | 타입 | 설명 | 제약조건 |
|---|---|---|---|
| `id` | INTEGER | 기본 키 | PRIMARY KEY, AUTOINCREMENT |
| `title` | TEXT | 기사 제목 | NOT NULL |
| `url` | TEXT | 기사 원문 URL | NOT NULL, UNIQUE |
| `source_name` | TEXT | 뉴스 소스 이름 (예: "TechCrunch") | NOT NULL |
| `source_url` | TEXT | RSS 피드 URL | — |
| `published_at` | DATETIME | 기사 발행 일시 | — |
| `collected_at` | DATETIME | 수집 일시 | NOT NULL, DEFAULT NOW |
| `description` | TEXT | RSS 피드 제공 원문 요약/본문 일부 | — |
| `summary_ko` | TEXT | AI 생성 한국어 요약 | — (실패 시 NULL) |
| `is_summarized` | BOOLEAN | 요약 완료 여부 | DEFAULT FALSE |

### 8.2 인덱스

```sql
CREATE INDEX idx_articles_collected_at ON articles (collected_at);
CREATE UNIQUE INDEX idx_articles_url ON articles (url);
```

### 8.3 SQLAlchemy 모델 예시

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    source_name = Column(String, nullable=False)
    source_url = Column(String)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, server_default=func.now(), nullable=False)
    description = Column(Text)
    summary_ko = Column(Text)
    is_summarized = Column(Boolean, default=False)
```

---

## 9. API 엔드포인트 목록 (API Endpoints)

| 메서드 | 경로 | 설명 | 응답 |
|---|---|---|---|
| `GET` | `/` | 오늘의 뉴스 홈 화면 (HTML) | Jinja2 렌더링 |
| `GET` | `/?date=YYYY-MM-DD` | 특정 날짜의 뉴스 (HTML) | Jinja2 렌더링 |
| `POST` | `/api/collect` | 즉시 뉴스 수집 트리거 | JSON |
| `GET` | `/api/articles` | 기사 목록 조회 (JSON) | JSON |
| `GET` | `/api/articles?date=YYYY-MM-DD` | 날짜 기준 기사 조회 | JSON |
| `GET` | `/health` | 서버 상태 확인 | JSON `{"status": "ok"}` |

### 9.1 POST /api/collect 응답 예시

```json
{
  "status": "success",
  "collected": 34,
  "summarized": 34,
  "skipped_duplicates": 12,
  "errors": 0,
  "duration_seconds": 187.3
}
```

### 9.2 GET /api/articles 응답 예시

```json
{
  "date": "2026-03-02",
  "total": 34,
  "articles": [
    {
      "id": 1,
      "title": "OpenAI Releases GPT-5",
      "url": "https://techcrunch.com/...",
      "source_name": "TechCrunch",
      "published_at": "2026-03-02T06:30:00Z",
      "collected_at": "2026-03-02T07:05:12Z",
      "summary_ko": "OpenAI가 GPT-5를 공개했다. 이번 모델은...",
      "is_summarized": true
    }
  ]
}
```

---

## 10. 뉴스 소스 목록 (News Sources & RSS URLs)

### 10.1 해외 소스

| 소스명 | RSS URL | 카테고리 |
|---|---|---|
| TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` | 해외 AI 뉴스 |
| VentureBeat AI | `https://venturebeat.com/category/ai/feed/` | 해외 AI 뉴스 |
| The Verge AI | `https://www.theverge.com/rss/ai-artificial-intelligence/index.xml` | 해외 AI 뉴스 |
| Google AI Blog | `https://blog.google/technology/ai/rss/` | 해외 AI 뉴스 |
| Google Research Blog | `https://research.google/blog/rss/` | 해외 AI 연구 |
| Anthropic News | `https://www.anthropic.com/news/rss` | 해외 AI 기업 |
| OpenAI Blog | `https://openai.com/blog/rss/` | 해외 AI 기업 |

### 10.2 국내 소스

| 소스명 | RSS URL | 카테고리 |
|---|---|---|
| ZDNet Korea | `https://zdnet.co.kr/rss/rss.aspx` | 국내 IT 뉴스 |
| 전자신문 (etnews) | `https://www.etnews.com/rss/` | 국내 IT 뉴스 |
| AI타임스 | `https://www.aitimes.com/rss/allArticle.xml` | 국내 AI 뉴스 |

> **참고**: RSS URL은 언론사 정책 변경에 따라 변경될 수 있다. 수집 오류 발생 시 최신 URL을 재확인해야 한다. URL은 `app/sources.py` 파일에 설정으로 관리하여 코드 수정 없이 업데이트 가능하도록 한다.

### 10.3 모니터링 대상 기업 키워드

수집된 기사의 연관 기업을 식별하기 위한 키워드 목록 (향후 필터링 기능에 활용):

| 분류 | 기업 키워드 |
|---|---|
| 미국 빅테크 | Nvidia, Tesla, Palantir, Microsoft, Apple, Google, Amazon, Meta |
| 미국 AI 기업 | OpenAI, Anthropic, Perplexity, Gemini, DeepMind |
| 한국 대기업 | 삼성, SK, LG, 현대, 롯데, GS, KT |
| 한국 AI 기업 | 네이버, 카카오, 업스테이지, 퓨리오사, 리벨리온, 포티투닷, 뤼튼 |

---

## 11. 개발 단계별 마일스톤 (Development Milestones)

### 전체 일정 요약

| 단계 | 기간 | 주요 산출물 |
|---|---|---|
| Phase 1: 기반 구축 | 1~2일차 | 프로젝트 구조, DB 모델, 환경 설정 |
| Phase 2: 뉴스 수집 | 3~4일차 | RSS 수집기, 중복 방지 로직 |
| Phase 3: AI 요약 | 5~6일차 | OpenRouter 연동, 요약 파이프라인 |
| Phase 4: 웹 UI | 7~9일차 | FastAPI 라우터, Jinja2 템플릿, CSS |
| Phase 5: 스케줄러 | 10일차 | APScheduler 통합, 자동화 완성 |
| Phase 6: 검증 및 배포 | 11~12일차 | 통합 테스트, 버그 수정, 배포 |

---

### Phase 1: 프로젝트 기반 구축 (1~2일차)

**목표**: 개발 환경 및 프로젝트 골격 완성

**태스크**:
- [ ] `requirements.txt` 작성 및 의존성 설치
- [ ] `app/database.py` — SQLAlchemy 엔진 및 세션 설정
- [ ] `app/models.py` — Article 모델 정의
- [ ] DB 마이그레이션 (테이블 자동 생성)
- [ ] `main.py` — FastAPI 앱 기본 골격
- [ ] `.env` 환경변수 로드 확인

**완료 기준**: FastAPI 서버가 `http://localhost:8000`에서 정상 응답함

---

### Phase 2: RSS 수집기 구축 (3~4일차)

**목표**: 10개 RSS 피드에서 기사 수집 및 DB 저장

**태스크**:
- [ ] `app/sources.py` — RSS 소스 목록 정의
- [ ] `app/fetcher.py` — feedparser 기반 수집 로직
- [ ] 중복 URL 방지 로직 구현
- [ ] 수집 결과 로깅
- [ ] 단위 테스트: 각 RSS 피드 수집 정상 작동 확인

**완료 기준**: 전체 피드 수집 후 DB에 기사가 저장되고 중복이 없음

---

### Phase 3: AI 요약 파이프라인 구축 (5~6일차)

**목표**: OpenRouter API로 수집된 기사 한국어 요약 생성

**태스크**:
- [ ] `app/summarizer.py` — OpenRouter API 호출 로직
- [ ] 요약 프롬프트 최적화
- [ ] Rate limit 대응 (요청 간 딜레이)
- [ ] API 실패 시 폴백 처리
- [ ] 단위 테스트: 샘플 기사로 요약 품질 검증

**완료 기준**: 기사 10건에 대해 한국어 요약이 정상 생성되고 DB에 저장됨

---

### Phase 4: 웹 UI 구축 (7~9일차)

**목표**: 뉴스 카드뷰 웹 인터페이스 완성

**태스크**:
- [ ] `app/routers/web.py` — 홈 및 날짜 필터 라우터
- [ ] `app/routers/api.py` — REST API 라우터
- [ ] `templates/base.html` — 기본 레이아웃
- [ ] `templates/index.html` — 홈 뉴스 목록
- [ ] `templates/components/card.html` — 기사 카드 컴포넌트
- [ ] `static/style.css` — 반응형 그리드 CSS
- [ ] 날짜 선택기 구현

**완료 기준**: 브라우저에서 오늘 날짜 뉴스 카드가 표시되고 날짜 필터가 동작함

---

### Phase 5: 스케줄러 통합 (10일차)

**목표**: 매일 오전 7시 자동 수집 파이프라인 완성

**태스크**:
- [ ] `app/scheduler.py` — APScheduler 작업 정의
- [ ] `main.py`에 스케줄러 시작 통합 (FastAPI lifespan event)
- [ ] `POST /api/collect` 수동 트리거 API 구현
- [ ] 스케줄러 정상 동작 확인 (로그 확인)

**완료 기준**: 서버 시작 후 오전 7시에 자동으로 수집이 실행됨 (또는 수동 API 호출로 즉시 실행 확인)

---

### Phase 6: 검증 및 마무리 (11~12일차)

**목표**: 전체 파이프라인 통합 테스트 및 배포 준비

**태스크**:
- [ ] 전체 E2E 테스트 (수집 → 요약 → DB 저장 → 웹 표시)
- [ ] 엣지 케이스 처리 확인 (피드 오류, API 실패, 빈 날짜 등)
- [ ] 로그 레벨 및 포맷 정리
- [ ] `README.md` 실행 가이드 작성
- [ ] 성능 점검 (홈 페이지 로딩 시간 측정)

**완료 기준**: 전체 파이프라인이 오류 없이 동작하고 README로 재현 가능함

---

## 12. 성공 지표 (Success Metrics / KPIs)

### 12.1 기술 지표

| KPI | 목표 | 측정 방법 |
|---|---|---|
| 일일 뉴스 수집 성공률 | 95% 이상 | 스케줄러 실행 로그 / 수집된 기사 수 |
| AI 요약 생성 성공률 | 90% 이상 | `is_summarized = TRUE` 비율 |
| URL 중복 수집률 | 0% | DB unique URL 검증 |
| 홈 페이지 로딩 시간 (p95) | 2초 이내 | 수동 측정 또는 간단한 벤치마크 |
| 하루 수집 기사 수 | 30건 이상 | DB 일별 count 쿼리 |

### 12.2 사용성 지표 (v1 이후 추적)

| KPI | 목표 | 측정 방법 |
|---|---|---|
| 일 평균 방문자 수 | 10명 이상 (사내 팀 기준) | 서버 액세스 로그 |
| 사용자 재방문율 | 70% 이상 (주 3회 이상) | 수동 피드백 |
| 요약 유용성 평가 | 긍정 피드백 80% 이상 | 팀 내 설문 또는 인터뷰 |

---

## 13. 리스크 및 완화 전략 (Risks & Mitigation)

| 리스크 | 발생 가능성 | 영향도 | 완화 전략 |
|---|---|---|---|
| OpenRouter 무료 모델 Rate Limit 초과 | 중간 | 높음 | 요청 간 딜레이 1초 + 폴백 모델 지정 |
| RSS 피드 URL 변경 또는 서비스 중단 | 낮음 | 중간 | `sources.py` 설정화, 수집 실패 시 알림 로그 |
| AI 요약 품질 저하 (짧은 RSS 본문) | 높음 | 중간 | 가능한 경우 전체 기사 크롤링 검토 (v2) |
| SQLite 동시 쓰기 충돌 | 낮음 | 중간 | 스케줄러와 API 요청의 동시 수집 방지 (Lock) |
| 국내 언론사 RSS 파싱 오류 (인코딩) | 중간 | 낮음 | feedparser의 인코딩 자동 처리 활용, 실패 시 스킵 |

---

## 14. 미결 사항 (Open Questions)

| # | 질문 | 담당자 | 상태 |
|---|---|---|---|
| 1 | AI타임스 RSS URL이 실제로 동작하는지 확인 필요 | 개발팀 | 미확인 |
| 2 | Anthropic, OpenAI 공식 블로그 RSS 존재 여부 확인 필요 | 개발팀 | 미확인 |
| 3 | OpenRouter 무료 모델 한국어 요약 품질 검증 필요 | 개발팀 | 미확인 |
| 4 | 수집 시각을 UTC 기준으로 할지 KST 기준으로 할지 결정 필요 | PM | 미결 |
| 5 | 기사 보관 기간 정책 필요 (30일? 90일? 무제한?) | PM | 미결 |
| 6 | 서버 운영 환경 결정 필요 (로컬 전용? 클라우드 배포?) | PM | 미결 |

---

*본 PRD는 v1 개발 기준으로 작성되었습니다. 개발 진행 중 요구사항 변경 시 이 문서를 업데이트하고 버전을 관리합니다.*
