# RSS 피드 크롤러
# feedparser를 사용하여 지정된 RSS 소스에서 기사를 수집하고
# SQLite DB에 저장한다. URL 기준 중복 방지 로직 포함.

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser

import app.supabase_db as db
from app.sources import (
    AI_KEYWORDS,
    AI_NATIVE_SOURCES,
    MAX_ARTICLES_PER_FEED,
    RSS_SOURCES,
    RSSSource,
)

logger = logging.getLogger(__name__)


def _parse_published_date(entry: feedparser.FeedParserDict) -> Optional[datetime]:
    """피드 엔트리에서 발행 일시를 파싱한다.

    feedparser는 published_parsed 또는 updated_parsed로 날짜를 제공한다.
    파싱에 실패하면 None을 반환한다.
    """
    # feedparser가 파싱한 time.struct_time 사용
    time_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if time_struct:
        try:
            return datetime(*time_struct[:6], tzinfo=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

    # RFC 2822 형식 문자열 직접 파싱 시도
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            return parsedate_to_datetime(raw).replace(tzinfo=None)
        except Exception:
            pass

    return None


def _extract_content(entry: feedparser.FeedParserDict) -> str:
    """피드 엔트리에서 기사 본문/요약을 추출한다.

    content > summary > description 순서로 우선 적용한다.
    HTML 태그는 최소한으로 정리한다.
    """
    # content 필드 (전체 본문이 있는 피드)
    if hasattr(entry, "content") and entry.content:
        raw = entry.content[0].get("value", "")
        if raw:
            return _strip_html(raw)[:2000]  # 요약 품질을 위해 2000자로 제한

    # summary 필드
    summary = getattr(entry, "summary", "") or ""
    if summary:
        return _strip_html(summary)[:2000]

    # description (일부 피드는 이 필드만 제공)
    description = getattr(entry, "description", "") or ""
    return _strip_html(description)[:2000]


def _strip_html(html: str) -> str:
    """HTML 태그를 제거하고 순수 텍스트를 반환한다."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        # bs4 실패 시 기본 치환
        import re
        clean = re.sub(r"<[^>]+>", " ", html)
        return " ".join(clean.split())


def _is_ai_related(title: str, description: str, source_name: str) -> bool:
    """기사가 AI 관련인지 키워드로 판단한다.

    AI 전용 소스(TechCrunch AI 등)는 항상 True를 반환한다.
    종합 IT 뉴스 소스는 키워드 매칭으로 판단한다.
    """
    if source_name in AI_NATIVE_SOURCES:
        return True

    text = (title + " " + description).lower()
    return any(kw.lower() in text for kw in AI_KEYWORDS)


def fetch_feed(source: RSSSource) -> dict:
    """단일 RSS 피드에서 기사를 수집하여 DB에 저장한다.

    Returns:
        dict: {
            "source": 소스명,
            "fetched": 피드에서 읽은 수,
            "saved": 실제 저장된 수,
            "skipped": 중복으로 건너뛴 수,
            "filtered": AI 무관으로 걸러진 수,
            "error": 에러 메시지 (성공 시 None)
        }
    """
    result = {
        "source": source.name,
        "fetched": 0,
        "saved": 0,
        "skipped": 0,
        "filtered": 0,
        "error": None,
    }

    try:
        logger.info(f"[{source.name}] RSS 수집 시작: {source.url}")

        # feedparser로 RSS 파싱 (타임아웃 10초)
        feed = feedparser.parse(
            source.url,
            agent="Mozilla/5.0 (AI Newsletter Bot)",
            request_headers={"Accept-Encoding": "gzip"},
        )

        if feed.bozo and not feed.entries:
            # bozo=True 이지만 entries가 있으면 부분 파싱 성공으로 처리
            raise ValueError(f"RSS 파싱 실패: {feed.bozo_exception}")

        entries = feed.entries[:MAX_ARTICLES_PER_FEED]
        result["fetched"] = len(entries)
        logger.info(f"[{source.name}] {len(entries)}건 피드 엔트리 읽음")

        for entry in entries:
            url = getattr(entry, "link", None)
            title = getattr(entry, "title", None)

            if not url or not title:
                logger.debug(f"[{source.name}] URL 또는 제목 없음, 건너뜀")
                result["filtered"] += 1
                continue

            # URL 정규화 (앞뒤 공백 및 트래킹 파라미터 제거)
            url = url.strip()

            # 중복 URL 체크
            if db.url_exists(url):
                logger.debug(f"[{source.name}] 중복 URL 건너뜀: {url[:80]}")
                result["skipped"] += 1
                continue

            description = _extract_content(entry)
            published_at = _parse_published_date(entry)

            # AI 관련 기사 필터링
            if not _is_ai_related(title, description, source.name):
                logger.debug(f"[{source.name}] AI 무관 기사 필터링: {title[:60]}")
                result["filtered"] += 1
                continue

            try:
                db.save_article({
                    "title": title.strip(),
                    "url": url,
                    "source_name": source.name,
                    "source_url": source.url,
                    "published_at": published_at.isoformat() if published_at else None,
                    "collected_at": datetime.utcnow().isoformat(),
                    "description": description,
                    "summary_ko": None,
                    "is_summarized": False,
                })
                result["saved"] += 1
                logger.info(f"[{source.name}] 저장 완료: {title[:60]}")
            except Exception as e:
                err = str(e)
                if "23505" in err or "unique" in err.lower():
                    result["skipped"] += 1
                    logger.debug(f"[{source.name}] DB UNIQUE 충돌 (동시 수집): {url[:60]}")
                else:
                    logger.error(f"[{source.name}] DB 저장 실패: {e}")
                    result["error"] = err

    except Exception as e:
        logger.error(f"[{source.name}] 피드 수집 오류: {e}", exc_info=True)
        result["error"] = str(e)

    logger.info(
        f"[{source.name}] 완료 — 수집: {result['fetched']}, "
        f"저장: {result['saved']}, 중복: {result['skipped']}, "
        f"필터: {result['filtered']}"
    )
    return result


def fetch_all_feeds() -> dict:
    """모든 활성화된 RSS 소스에서 기사를 수집한다.

    하나의 소스에서 실패해도 나머지 소스 수집은 계속 진행한다.

    Returns:
        dict: 전체 수집 결과 집계
    """
    start_time = time.time()
    active_sources = [s for s in RSS_SOURCES if s.enabled]

    logger.info(f"전체 RSS 수집 시작 — 소스 수: {len(active_sources)}")

    total_saved = 0
    total_skipped = 0
    total_filtered = 0
    errors = []

    for source in active_sources:
        result = fetch_feed(source)
        total_saved += result["saved"]
        total_skipped += result["skipped"]
        total_filtered += result["filtered"]
        if result["error"]:
            errors.append({"source": source.name, "error": result["error"]})

        # 피드 간 딜레이: 서버 부하 방지 및 rate limit 회피
        time.sleep(0.5)

    duration = time.time() - start_time

    summary = {
        "total_sources": len(active_sources),
        "total_saved": total_saved,
        "total_skipped_duplicates": total_skipped,
        "total_filtered": total_filtered,
        "error_count": len(errors),
        "errors": errors,
        "duration_seconds": round(duration, 2),
    }

    logger.info(
        f"전체 수집 완료 — "
        f"저장: {total_saved}, 중복: {total_skipped}, "
        f"필터: {total_filtered}, 오류: {len(errors)}, "
        f"소요시간: {duration:.1f}초"
    )
    return summary
