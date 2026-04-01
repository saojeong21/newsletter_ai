# Obsidian 저널 스크랩 기능 설계

**날짜:** 2026-04-01  
**상태:** 승인됨 (수정 1차)

---

## 개요

뉴스레터 웹앱(Vercel 배포)에서 기사 카드의 스크랩 버튼을 클릭하면, 원문 URL에서 핵심 본문을 추출하여 로컬 Obsidian 저널(`02-Areas/Journal/YYYY-MM-DD.md`)에 날짜별로 저장한다. 데스크탑/모바일 브라우저 모두 지원한다.

---

## 아키텍처

```
브라우저 (Vercel 배포 URL — 데스크탑 or 모바일)
    │
    ├─ 스크랩 버튼 클릭
    │    → 카드 DOM에서 {title, url, source_name} 읽기
    │    → localStorage에서 에이전트 URL 읽기
    │         (기본값: http://localhost:27123)
    │         (모바일 시: http://192.168.x.x:27123 으로 변경)
    │
    └─ POST {agent_url}/scrap
              │
              └─ obsidian_agent.py (로컬 HTTP 데몬, 0.0.0.0:27123)
                    ├─ 원문 URL 크롤링 (trafilatura)
                    ├─ 본문 추출 (광고/헤더/네비 제외)
                    └─ Obsidian 파일 저장 / append
                         ~/문서/Obsidian/02-Areas/Journal/YYYY-MM-DD.md
```

**핵심 제약:** Vercel 서버는 수정하지 않는다. 브라우저가 카드의 기사 데이터를 직접 로컬 데몬으로 전송한다.

**모바일 지원 방식:** 데몬을 `0.0.0.0`으로 바인딩하여 LAN 전체에서 접근 가능하게 한다. 웹앱 설정에서 에이전트 URL을 변경할 수 있으며 `localStorage`에 저장된다.

---

## 구성 요소

### 새로 만들 파일

| 파일 | 역할 |
|---|---|
| `obsidian_agent.py` | 로컬 HTTP 데몬 (Flask, 0.0.0.0:27123) |

### 수정할 파일

| 파일 | 변경 내용 |
|---|---|
| `app/templates/index.html` | 기사 카드에 스크랩 버튼 추가, 에이전트 URL 설정 UI, JS 스크랩 로직 |
| `app/static/style.css` | 스크랩 버튼 스타일, 로딩/성공 상태, 설정 UI 스타일 |
| `public/static/style.css` | 위와 동일 (Vercel CDN 동기화) |

---

## 데이터 흐름

1. 사용자가 기사 카드의 스크랩 버튼 클릭
2. 브라우저 JS가 카드 DOM에서 `{title, url, source_name}` 추출
3. `localStorage`에서 에이전트 URL 읽기 (없으면 `http://localhost:27123`)
4. `POST {agent_url}/scrap` 요청 전송
5. 로컬 데몬이 `url`을 크롤링하여 `trafilatura`로 본문 추출
6. 크롤링 실패 시 → HTTP 422 반환 → 브라우저 에러 토스트 표시 (저장 안 함)
7. 성공 시 → Obsidian 파일에 append → HTTP 200 → 브라우저 성공 표시

---

## Obsidian 저장 형식

파일 경로: `/Users/brandon_s/문서/Obsidian/02-Areas/Journal/YYYY-MM-DD.md`

- **같은 날짜의 모든 기사는 하나의 파일에 누적 저장** (append)
- 파일이 없으면 frontmatter + 헤더 포함하여 새로 생성
- 기사 간 구분선(`---`)으로 명확히 분리

```markdown
---
date: 2026-04-01
tags: [AI, newsletter]
---

# 2026-04-01 AI 뉴스 스크랩

## [OpenAI releases GPT-5](https://techcrunch.com/...)
> 출처: TechCrunch · 스크랩: 09:14

OpenAI has released GPT-5, a new model that significantly improves reasoning...
[trafilatura로 추출한 핵심 본문]

---

## [다음 기사 제목](url)
> 출처: VentureBeat · 스크랩: 09:32

...

---
```

---

## UX / 오류 처리

| 상황 | 브라우저 동작 |
|---|---|
| 버튼 클릭 직후 | 로딩 스피너 표시 |
| 성공 | ✓ 아이콘으로 변경 + "Obsidian에 저장됨" 토스트 (재클릭 방지) |
| 크롤링 실패 | "본문을 가져올 수 없습니다" 에러 토스트 (저장 안 함) |
| 데몬 미실행 / 연결 실패 | "obsidian_agent.py를 먼저 실행하세요" 에러 토스트 |

### 에이전트 URL 설정 UI

- 페이지 상단 또는 설정 아이콘(⚙)으로 접근
- 입력 필드: 에이전트 URL (기본값 `http://localhost:27123`)
- 저장 버튼 → `localStorage`에 `obsidian_agent_url` 키로 저장
- 모바일 사용 시 데스크탑 LAN IP로 변경 (`http://192.168.x.x:27123`)

---

## obsidian_agent.py 상세

- **런타임:** Python, Flask
- **바인딩:** `0.0.0.0:27123` (LAN 전체 접근 가능, 모바일 지원)
- **CORS 허용 출처:** `https://newsletter-ai-saojeong21s-projects.vercel.app`, `http://localhost:*`
- **의존성:** `flask`, `trafilatura`, `flask-cors`

### 엔드포인트

`POST /scrap`

요청 바디:
```json
{
  "title": "기사 제목",
  "url": "https://techcrunch.com/...",
  "source_name": "TechCrunch"
}
```

응답 (성공):
```json
{"status": "ok", "file": "2026-04-01.md"}
```

응답 (크롤링 실패):
```json
{"error": "본문을 가져올 수 없습니다"}
```

### 실행 방법

```bash
pip install flask flask-cors trafilatura
python obsidian_agent.py
# → "Obsidian Agent running on http://0.0.0.0:27123"
# → "LAN access: http://192.168.x.x:27123"
```

---

## 범위 외 (이번 구현에서 제외)

- 이미 스크랩된 기사 중복 체크 (DB 기반 추적)
- Vercel 배포 환경에서의 서버사이드 저장
