# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Newsletter** — 매일 아침 국내외 주요 AI 관련 뉴스를 자동으로 수집하여 보여주는 웹 애플리케이션.

---

## 완료된 작업

- [x] 프로젝트 디렉토리 초기화
- [x] `.env` 파일에 API 키 설정 (OpenRouter, SQLite DB)
- [x] `.gitignore` 생성 — `.env` 및 빌드 산출물 제외
- [x] `.env.example` 생성 — 키 목록 템플릿 (커밋 가능)
- [x] `CLAUDE.md` 작성

---

## 다음 작업

### 웹 애플리케이션 구축

매일 아침 국내외 주요 AI 뉴스를 수집·요약·표시하는 웹 앱을 만든다.

#### 목표 기능

- 뉴스 수집: RSS 피드 또는 웹 크롤링으로 국내외 AI 뉴스 소스에서 기사 수집
- 소집 뉴스 대상 기업 : 미국 빅테크 (Nvidia, Tesla, Palantir, Microsoft, Apple, Google, Amazon, Meta 등)/미국 주요 AI 기업 (OpenAI, Google Gemini, Anthropic, Perplexity AI 등)/한국 대기업 (삼성, SK, LG, 현대, 롯데, GS, KT등)/한국 AI 기업 (네이버, 카카오, 업스테이지, 퓨리오사 AI, 리벨리온, 포티투닷, 뤼튼 등)
- AI 요약: OpenRouter API를 통해 각 기사를 한국어로 간략 요약
- 웹 UI: 오늘의 주요 AI 뉴스를 카드 형태로 표시
- 자동화: 매일 아침 정해진 시간에 자동 수집 (스케줄러 또는 cron)
- 저장: 수집된 기사와 요약을 SQLite DB에 보관

#### 프롬프트 (다음 세션 시작 시 사용)

```
매일 아침 국내외 주요 AI 뉴스를 자동 수집하고 한국어로 요약해서 보여주는 웹 애플리케이션을 만들어줘.

[요구사항]
- 뉴스 소스: TechCrunch AI, VentureBeat AI, The Verge AI, Google AI Blog 등 RSS 피드 + 국내 IT 뉴스(ZDNet Korea, AI타임스 등)
- 수집 주기: 매일 오전 7시 자동 실행 (APScheduler 또는 cron)
- AI 요약: OpenRouter API(환경변수 OPENROUTER_API_KEY)로 각 기사를 한국어 요약 생성
- DB: SQLite(환경변수 DATABASE_URL)에 기사 원문, 요약, 출처, 수집일시 저장
- 웹 UI: FastAPI + Jinja2 또는 Flask로 오늘의 뉴스를 카드 형태로 표시, 날짜별 필터링 지원
- 중복 방지: URL 기준으로 이미 수집된 기사는 재수집 안 함

[기술 스택 우선순위]
- 백엔드: Python (FastAPI 선호)
- 프론트엔드: 서버사이드 렌더링 (Jinja2 템플릿), 별도 JS 프레임워크 없이 심플하게
- 의존성 관리: requirements.txt 또는 pyproject.toml

[환경]
- .env 파일에 OPENROUTER_API_KEY, DATABASE_URL 이미 설정되어 있음
- python-dotenv로 환경변수 로드
```

---

## Environment Setup

`.env.example`을 복사하여 `.env`를 만들고 실제 키를 입력:

```
cp .env.example .env
```

`.env`는 `.gitignore`에 포함되어 있어 **절대 커밋되지 않음**. `.env.example`만 버전 관리에 포함.

### Required Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM access |
| `DATABASE_URL` | SQLite database path (default: `sqlite:///app.db`) |
