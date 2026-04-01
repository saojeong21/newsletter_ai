# Obsidian 저널 스크랩 기능 설계

**날짜:** 2026-04-01  
**상태:** 승인됨

---

## 개요

뉴스레터 웹앱(Vercel 배포)에서 기사 카드의 스크랩 버튼을 클릭하면, 원문 URL에서 핵심 본문을 추출하여 로컬 Obsidian 저널(`02-Areas/Journal/YYYY-MM-DD.md`)에 날짜별로 저장한다.

---

## 아키텍처

```
브라우저 (Vercel 배포 URL)
    │
    ├─ 스크랩 버튼 클릭
    │    → 카드 DOM에서 {title, url, source_name} 읽기
    │
    └─ POST http://localhost:27123/scrap
              │
              └─ obsidian_agent.py (로컬 HTTP 데몬)
                    ├─ 원문 URL 크롤링 (trafilatura)
                    ├─ 본문 추출 (광고/헤더/네비 제외)
                    └─ Obsidian 파일 저장 / append
                         ~/문서/Obsidian/02-Areas/Journal/YYYY-MM-DD.md
```

**핵심 제약:** Vercel 서버는 수정하지 않는다. 브라우저가 카드의 기사 데이터를 직접 로컬 데몬으로 전송한다.

---

## 구성 요소

### 새로 만들 파일

| 파일 | 역할 |
|---|---|
| `obsidian_agent.py` | 로컬 HTTP 데몬 (Flask, localhost:27123) |

### 수정할 파일

| 파일 | 변경 내용 |
|---|---|
| `app/templates/index.html` | 기사 카드에 스크랩 버튼 추가, JS 스크랩 로직 |
| `app/static/style.css` | 스크랩 버튼 스타일, 로딩/성공 상태 |
| `public/static/style.css` | 위와 동일 (Vercel CDN 동기화) |

---

## 데이터 흐름

1. 사용자가 기사 카드의 스크랩 버튼 클릭
2. 브라우저 JS가 카드 DOM에서 `{title, url, source_name}` 추출
3. `POST http://localhost:27123/scrap` 요청 전송
4. 로컬 데몬이 `url`을 크롤링하여 `trafilatura`로 본문 추출
5. 크롤링 실패 시 → HTTP 422 반환 → 브라우저 에러 토스트 표시 (저장 안 함)
6. 성공 시 → Obsidian 파일에 append → HTTP 200 → 브라우저 성공 표시

---

## Obsidian 저장 형식

파일 경로: `/Users/brandon_s/문서/Obsidian/02-Areas/Journal/YYYY-MM-DD.md`

- 파일이 없으면 frontmatter + 헤더 포함하여 새로 생성
- 파일이 있으면 기존 내용 뒤에 append

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
```

---

## UX / 오류 처리

| 상황 | 브라우저 동작 |
|---|---|
| 버튼 클릭 직후 | 로딩 스피너 표시 |
| 성공 | ✓ 아이콘으로 변경 + "Obsidian에 저장됨" 토스트 (재클릭 방지) |
| 크롤링 실패 | "본문을 가져올 수 없습니다" 에러 토스트 (저장 안 함) |
| 데몬 미실행 | "obsidian_agent.py를 먼저 실행하세요" 에러 토스트 |

---

## obsidian_agent.py 상세

- **런타임:** Python, Flask
- **포트:** 27123
- **CORS 허용 출처:** `https://newsletter-ai-saojeong21s-projects.vercel.app`, `http://localhost:8000`
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
# → "Obsidian Agent running on http://localhost:27123"
```

---

## 범위 외 (이번 구현에서 제외)

- 이미 스크랩된 기사 중복 체크 (DB 기반 추적)
- 모바일 지원
- Vercel 배포 환경에서의 서버사이드 저장
