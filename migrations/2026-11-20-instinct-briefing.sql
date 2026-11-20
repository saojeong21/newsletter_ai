-- Instinct 브리핑 연동 마이그레이션 (2026-11-20)
-- Supabase 대시보드 > SQL Editor에서 실행하세요.
-- 두 컬럼 모두 nullable이라 기존 데이터와 동작에는 영향이 없습니다.

-- 1) 기사 원문 전문 보관용.
--    LinkedIn 포스트·채용 공고·유료 기사처럼 MacBook 에이전트가 다시 수집할 수 없는
--    본문을 브리핑 적재 시 함께 저장합니다.
alter table ainewsletter_items
    add column if not exists full_text text;

-- 2) 스크랩 큐에 전문 전달용.
--    content가 있으면 obsidian_agent가 본문 재수집(trafilatura)을 건너뛰고 이 값을 사용합니다.
alter table scrap_queue
    add column if not exists content text;
