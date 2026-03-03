import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from sqlalchemy.orm import Session

from app.models import Article
from app.sources import AI_KEYWORDS, AI_NATIVE_SOURCES, MAX_ARTICLES_PER_FEED, RSS_SOURCES, RSSSource

logger = logging.getLogger(__name__)


def _parse_published_date(entry):
    time_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if time_struct:
        try:
            return datetime(*time_struct[:6], tzinfo=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            return parsedate_to_datetime(raw).replace(tzinfo=None)
        except Exception:
            pass
    return None


def _extract_content(entry):
    if hasattr(entry, "content") and entry.content:
        raw = entry.content[0].get("value", "")
        if raw:
            return _strip_html(raw)[:2000]
    summary = getattr(entry, "summary", "") or ""
    if summary:
        return _strip_html(summary)[:2000]
    return _strip_html(getattr(entry, "description", "") or "")[:2000]


def _strip_html(html):
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        import re
        return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _is_ai_related(title, description, source_name):
    if source_name in AI_NATIVE_SOURCES:
        return True
    text = (title + " " + description).lower()
    return any(kw.lower() in text for kw in AI_KEYWORDS)


def _url_exists(db, url):
    return db.query(Article).filter(Article.url == url).first() is not None


def fetch_feed(source: RSSSource, db: Session) -> dict:
    result = {"source": source.name, "fetched": 0, "saved": 0, "skipped": 0, "filtered": 0, "error": None}

    try:
        logger.info(f"[{source.name}] RSS 수집 시작: {source.url}")
        feed = feedparser.parse(source.url, agent="Mozilla/5.0 (AI Newsletter Bot)", request_headers={"Accept-Encoding": "gzip"})

        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS 파싱 실패: {feed.bozo_exception}")

        entries = feed.entries[:MAX_ARTICLES_PER_FEED]
        result["fetched"] = len(entries)

        for entry in entries:
            url = getattr(entry, "link", None)
            title = getattr(entry, "title", None)

            if not url or not title:
                result["filtered"] += 1
                continue

            url = url.strip()
            if _url_exists(db, url):
                result["skipped"] += 1
                continue

            description = _extract_content(entry)
            if not _is_ai_related(title, description, source.name):
                result["filtered"] += 1
                continue

            article = Article(
                title=title.strip(), url=url, source_name=source.name,
                source_url=source.url, published_at=_parse_published_date(entry),
                collected_at=datetime.utcnow(), description=description,
                summary_ko=None, is_summarized=False,
            )
            db.add(article)

            try:
                db.commit()
                db.refresh(article)
                result["saved"] += 1
            except Exception as e:
                db.rollback()
                if "UNIQUE" in str(e).upper():
                    result["skipped"] += 1
                else:
                    logger.error(f"[{source.name}] DB 저장 실패: {e}")
                    result["error"] = str(e)

    except Exception as e:
        db.rollback()
        logger.error(f"[{source.name}] 피드 수집 오류: {e}", exc_info=True)
        result["error"] = str(e)

    logger.info(f"[{source.name}] 완료 — 수집: {result['fetched']}, 저장: {result['saved']}, 중복: {result['skipped']}, 필터: {result['filtered']}")
    return result


def fetch_all_feeds(db: Session) -> dict:
    start_time = time.time()
    active_sources = [s for s in RSS_SOURCES if s.enabled]
    logger.info(f"전체 RSS 수집 시작 — 소스 수: {len(active_sources)}")

    total_saved = total_skipped = total_filtered = 0
    errors = []

    for source in active_sources:
        result = fetch_feed(source, db)
        total_saved += result["saved"]
        total_skipped += result["skipped"]
        total_filtered += result["filtered"]
        if result["error"]:
            errors.append({"source": source.name, "error": result["error"]})
        time.sleep(0.5)

    duration = time.time() - start_time
    summary = {
        "total_sources": len(active_sources), "total_saved": total_saved,
        "total_skipped_duplicates": total_skipped, "total_filtered": total_filtered,
        "error_count": len(errors), "errors": errors, "duration_seconds": round(duration, 2),
    }
    logger.info(f"전체 수집 완료 — 저장: {total_saved}, 중복: {total_skipped}, 필터: {total_filtered}, 오류: {len(errors)}, 소요시간: {duration:.1f}초")
    return summary
