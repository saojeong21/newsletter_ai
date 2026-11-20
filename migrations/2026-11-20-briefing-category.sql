-- Instinct 브리핑 카테고리 컬럼 추가
-- /instinct-briefing 페이지의 섹션 그룹핑에 사용한다.
-- Supabase 대시보드 SQL 에디터에서 실행.

alter table ainewsletter_items
    add column if not exists category text;

create index if not exists idx_ainewsletter_items_category
    on ainewsletter_items (category);
