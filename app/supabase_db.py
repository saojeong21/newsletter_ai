# Supabase 데이터 접근 계층
# supabase-py 클라이언트를 사용하여 ainewsletter_items 테이블 CRUD 수행

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

logger = logging.getLogger(__name__)

TABLE = "ainewsletter_items"

_client: Optional[Client] = None


def get_client() -> Client:
    """싱글턴 Supabase 클라이언트를 반환한다."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL 및 SUPABASE_ANON_KEY 환경변수가 설정되지 않았습니다."
            )
        _client = create_client(url, key)
    return _client


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """ISO 8601 문자열을 timezone-naive UTC datetime으로 변환한다."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


@dataclass
class ArticleRow:
    """ainewsletter_items 행을 나타내는 데이터 클래스.

    SQLAlchemy ORM 객체와 동일한 속성명을 사용하여
    기존 템플릿 코드와 호환성을 유지한다.
    """

    id: Optional[int] = None
    title: str = ""
    url: str = ""
    source_name: str = ""
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    description: Optional[str] = None
    summary_ko: Optional[str] = None
    is_summarized: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "ArticleRow":
        return cls(
            id=d.get("id"),
            title=d.get("title", ""),
            url=d.get("url", ""),
            source_name=d.get("source_name", ""),
            source_url=d.get("source_url"),
            published_at=_parse_dt(d.get("published_at")),
            collected_at=_parse_dt(d.get("collected_at")),
            description=d.get("description"),
            summary_ko=d.get("summary_ko"),
            is_summarized=d.get("is_summarized", False),
        )


def url_exists(url: str) -> bool:
    """URL이 이미 DB에 존재하는지 확인한다."""
    result = get_client().table(TABLE).select("id").eq("url", url).limit(1).execute()
    return len(result.data) > 0


def save_article(data: dict) -> Optional[ArticleRow]:
    """기사를 DB에 저장하고 저장된 행을 반환한다.

    URL 중복 시 PostgREST가 23505 에러를 발생시키므로 호출 전에
    url_exists()로 중복 여부를 확인하거나 예외를 처리해야 한다.
    """
    try:
        result = get_client().table(TABLE).insert(data).execute()
        return ArticleRow.from_dict(result.data[0]) if result.data else None
    except Exception as e:
        logger.error(f"기사 저장 실패: {e}")
        raise


def get_articles_by_date(target_date: date) -> List[ArticleRow]:
    """KST 기준 특정 날짜에 수집된 기사를 반환한다.

    collected_at은 UTC로 저장되므로 KST(UTC+9) 자정을 UTC 범위로 변환한다.
    """
    kst_offset = timedelta(hours=9)
    start_utc = datetime.combine(target_date, datetime.min.time()) - kst_offset
    end_utc = start_utc + timedelta(days=1)

    result = (
        get_client()
        .table(TABLE)
        .select("*")
        .gte("collected_at", start_utc.isoformat())
        .lt("collected_at", end_utc.isoformat())
        .order("collected_at", desc=True)
        .execute()
    )
    return [ArticleRow.from_dict(row) for row in result.data]


def get_unsummarized_articles() -> List[ArticleRow]:
    """요약되지 않은 기사 목록을 반환한다."""
    result = (
        get_client()
        .table(TABLE)
        .select("*")
        .eq("is_summarized", False)
        .order("collected_at", desc=True)
        .execute()
    )
    return [ArticleRow.from_dict(row) for row in result.data]


def update_summary(article_id: int, summary_ko: Optional[str]) -> bool:
    """기사 요약을 업데이트하고 is_summarized를 True로 설정한다."""
    try:
        get_client().table(TABLE).update(
            {"summary_ko": summary_ko, "is_summarized": True}
        ).eq("id", article_id).execute()
        return True
    except Exception as e:
        logger.error(f"요약 업데이트 실패 (id={article_id}): {e}")
        return False


def get_available_dates(limit: int = 30) -> List[str]:
    """기사가 수집된 날짜 목록을 KST 기준 최근 순으로 반환한다."""
    result = (
        get_client()
        .table(TABLE)
        .select("collected_at")
        .order("collected_at", desc=True)
        .limit(limit * 50)
        .execute()
    )

    kst_offset = timedelta(hours=9)
    seen: set = set()
    dates: List[str] = []

    for row in result.data:
        raw = row.get("collected_at")
        if not raw:
            continue
        dt_utc = _parse_dt(raw)
        if dt_utc is None:
            continue
        date_str = (dt_utc + kst_offset).date().isoformat()
        if date_str not in seen:
            seen.add(date_str)
            dates.append(date_str)
        if len(dates) >= limit:
            break

    return dates


def get_stats() -> dict:
    """DB에 저장된 기사 통계를 반환한다."""
    client = get_client()

    total_result = client.table(TABLE).select("id", count="exact").execute()
    total = total_result.count or 0

    summarized_result = (
        client.table(TABLE)
        .select("id", count="exact")
        .not_.is_("summary_ko", "null")
        .execute()
    )
    summarized = summarized_result.count or 0

    sources_result = client.table(TABLE).select("source_name").execute()
    source_counts: dict = {}
    for row in sources_result.data:
        name = row["source_name"]
        source_counts[name] = source_counts.get(name, 0) + 1

    return {
        "total_articles": total,
        "summarized": summarized,
        "unsummarized": total - summarized,
        "sources": [{"name": k, "count": v} for k, v in source_counts.items()],
    }
