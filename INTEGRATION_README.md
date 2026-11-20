# Instinct 브리핑 연동 — 적용 안내 (2026-11-20)

이 변경 세트는 뉴스레터 앱에 "Instinct 브리핑" 소스를 추가합니다. 적용 후 Instinct 에이전트가
매일 아침 브리핑 항목(제목·요약·원문 전문·링크)을 POST하면 앱의 다른 기사처럼 카드로 표시되고,
기존 🔖 스크랩 버튼 → scrap_queue → MacBook 에이전트 → Obsidian 저장 경로가 그대로 동작합니다.

## 변경 내용

| 파일 | 변경 |
| --- | --- |
| `migrations/2026-11-20-instinct-briefing.sql` | `ainewsletter_items.full_text`, `scrap_queue.content` 컬럼 추가 (둘 다 nullable) |
| `app/main.py` | `POST /api/briefing` 신규 (CRON_SECRET 인증), `POST /api/scrap`가 full_text를 큐에 함께 실음 |
| `app/supabase_db.py` | `save_briefing_item()`, `get_article_full_text()` 추가, `enqueue_scrap()`에 content 지원, pending 조회 select에 content 포함 |
| `obsidian_agent.py` | 큐의 content가 있으면 본문 재수집 생략, 저장 폴더를 `02-Areas/Journal` → `02-Areas/News`로 변경 |
| `app/templates/index.html`, `app/templates/news.html` | 브리핑 카드에 보라색 "Instinct" 태그 표시 |
| `app/static/style.css`, `public/static/style.css` | `.tag-region.instinct` 스타일 |
| `.env.example` | `CRON_SECRET`, `SUPABASE_SERVICE_ROLE_KEY` 문서화 |

## 적용 순서

1. **SQL 실행** — Supabase 대시보드 > SQL Editor에서
   `migrations/2026-11-20-instinct-briefing.sql` 내용을 실행.
   (코드 배포보다 먼저 실행해야 /api/briefing이 정상 동작합니다. 순서가 뒤집혀도 /api/scrap 쪽은
   방어 코드가 있어 기존 스크랩은 계속 동작합니다.)
2. **코드 반영** — 이 변경을 검토 후 평소 배포 흐름대로 반영 (git push → Vercel 자동 배포).
3. **MacBook 에이전트 재시작** — 새 코드를 pull한 뒤 `python obsidian_agent.py` 재실행.
   이후 스크랩 노트는 `~/Documents/Obsidian/02-Areas/News/YYYY-MM-DD.md`에 저장됩니다.
   (기존 00-Inbox/Morning Briefing_Instinct 노트 이동은 사용자가 직접 진행 중)
4. **Instinct에 완료 알림** — 배포가 끝나면 알려 주세요. 이후 아침 브리핑 POST가 시작됩니다.

## 환경 변수

- 앱에 새로 필요한 변수는 없습니다. `CRON_SECRET`은 기존 값을 그대로 사용합니다
  (`/api/cron/collect`, `/api/scrap/pending` 등과 동일한 Bearer 인증).
- Instinct가 `/api/briefing`을 호출할 때는 `CRON_SECRET`과 Vercel 보호 우회용
  `VERCEL_BYPASS_SECRET` 두 개가 필요합니다 (정식 배포가 로그인 보호 도메인이라서).
  두 값은 vault 링크로 안전하게 전달받을 예정이며 채팅으로는 받지 않습니다.

## 동작 방식 메모

- `/api/briefing` 요청 형식:
  ```json
  {
    "date": "2026-11-21",
    "source_url": "https://files.instinct.com/...",
    "items": [
      { "title": "…", "url": "https://…", "summary": "…", "fulltext": "…(선택)" }
    ]
  }
  ```
  URL 기준으로 중복은 건너뛰고, 응답은 `{ inserted, skipped, errors }`.
- 브리핑 카드는 `source_name="Instinct 브리핑"`으로 저장되어 당일 홈 상단에 표시됩니다.
- "Instinct" 태그는 국내/해외 어느 쪽에도 속하지 않는 별도 태그입니다. 지역 필터에서
  전체(기본) 보기에는 항상 표시되고, 국내·해외 필터를 켜면 숨겨집니다
  (어느 한쪽으로 잘못 분류되는 것보다 이 쪽이 덜 어색하다고 판단).
- 브리핑 항목의 `is_summarized`는 false로 저장해 기존 "AI 요약" 배지(OpenRouter 3줄 요약)와
  구분합니다. 요약문은 브리핑이 만든 문장이 카드에 그대로 표시됩니다.
- full_text가 있는 항목을 스크랩하면 MacBook 에이전트가 재수집 없이 그 전문을 저장합니다.
  LinkedIn·채용 공고처럼 로그인 뒤의 원문도 저장되는 경로입니다.
