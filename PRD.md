# AI 뉴스레터 웹 애플리케이션 PRD

**문서 버전**: 1.0  
**작성일**: 2026-03-02  
**상태**: 초안 (Draft)

---

## 1. 개요

### 1.1 제품 비전

> "매일 아침, 바쁜 AI 종사자와 관심자가 전 세계 주요 AI 뉴스를 5분 안에 파악할 수 있도록 한다."

### 1.2 목표

| 목표 | 핵심 결과 |
|---|---|
| 신뢰할 수 있는 뉴스 자동 수집 | 매일 오전 7시 기준 수집 성공률 95% 이상 |
| 사용자 편의성 향상 | 기사 한국어 요약 제공률 100% |
| 중복 콘텐츠 최소화 | URL 기준 중복 수집률 0% |
| 빠른 콘텐츠 탐색 | 홈 페이지 로딩 2초 이내 |

---

## 2. 기능 요구사항 (MoSCoW)

| 우선순위 | 기능 |
|---|---|
| **Must-have** | RSS 피드 자동 수집 |
| **Must-have** | AI 한국어 요약 생성 |
| **Must-have** | SQLite DB 저장 및 중복 방지 |
| **Must-have** | 웹 UI 카드뷰 (오늘의 뉴스) |
| **Must-have** | 날짜별 필터링 |
| **Should-have** | 수동 수집 트리거 (API) |
| **Could-have** | 키워드 검색 기능 |
| **Won't-have (v1)** | 사용자 로그인 및 개인화 |
| **Won't-have (v1)** | 이메일 뉴스레터 발송 |

---

## 3. 기술 스택

| 레이어 | 기술 | 버전 |
|---|---|---|
| 웹 프레임워크 | FastAPI | 0.115.x |
| 템플릿 엔진 | Jinja2 | 3.x |
| ORM | SQLAlchemy | 2.x |
| DB | SQLite | 3.x |
| RSS 파싱 | feedparser | 6.x |
| HTTP 클라이언트 | httpx | 0.27.x |
| 스케줄러 | APScheduler | 3.x |

---

## 4. 데이터 모델

### Articles 테이블

| 컨럼명 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER | 기본 키 |
| `title` | TEXT | 기사 제목 |
| `url` | TEXT | 기사 원문 URL (UNIQUE) |
| `source_name` | TEXT | 뉴스 소스 이름 |
| `source_url` | TEXT | RSS 피드 URL |
| `published_at` | DATETIME | 기사 발행 일시 |
| `collected_at` | DATETIME | 수집 일시 |
| `description` | TEXT | RSS 제공 본문/요약 |
| `summary_ko` | TEXT | AI 생성 한국어 요약 |
| `is_summarized` | BOOLEAN | 요약 완료 여부 |

---

## 5. API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 오늘의 뉴스 홈 화면 (HTML) |
| GET | `/?date=YYYY-MM-DD` | 특정 날짜의 뉴스 |
| POST | `/api/collect` | 즉시 뉴스 수집 트리거 |
| GET | `/api/articles` | 기사 목록 조회 (JSON) |
| GET | `/health` | 서버 상태 확인 |
| GET | `/api/stats` | 수집 통계 |
