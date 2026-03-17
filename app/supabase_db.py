# Supabase 데이터 접근 계층
# httpx로 Supabase PostgREST API를 직접 호출한다.
# supabase-py의 HTTP/2 호환 문제를 우회하기 위해 http2=False로 강제.

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TABLE = "ainewsletter_items"


def _base_url() -> str:
    return f"{os.getenv('SUPABASE_URL', '')}/rest/v1"


def _headers() -> dict:
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _service_headers() -> dict:
    """쓰기 작업(INSERT/UPDATE/DELETE)에 사용 — service_role key 필요."""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        # fallback: anon key (로컬 개발 등 service key 미설정 시)
        key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _client() -> httpx.Client:
    return httpx.Client(http2=False, timeout=30)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


@dataclass
class ArticleRow:
    """ainewsletter_items 행을 나타내는 데이터 클래스."""

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
    with _client() as c:
        resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers=_headers(),
            params={"url": f"eq.{url}", "select": "id", "limit": "1"},
        )
        resp.raise_for_status()
        return len(resp.json()) > 0


def save_article(data: dict) -> Optional[ArticleRow]:
    with _client() as c:
        resp = c.post(
            f"{_base_url()}/{TABLE}",
            headers=_service_headers(),
            json=data,
        )
        resp.raise_for_status()
        result = resp.json()
        return ArticleRow.from_dict(result[0]) if result else None


def get_articles_by_date(target_date: date) -> List[ArticleRow]:
    kst_offset = timedelta(hours=9)
    start_utc = datetime.combine(target_date, datetime.min.time()) - kst_offset
    end_utc = start_utc + timedelta(days=1)

    with _client() as c:
        resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers=_headers(),
            params={
                "collected_at": f"gte.{start_utc.isoformat()}",
                "and": f"(collected_at.lt.{end_utc.isoformat()})",
                "order": "collected_at.desc",
                "select": "*",
            },
        )
        resp.raise_for_status()
        return [ArticleRow.from_dict(row) for row in resp.json()]


def get_unsummarized_articles(limit: int = 100) -> List[ArticleRow]:
    """미요약 기사를 최신순으로 반환한다. limit으로 DB 쿼리 자체를 제한한다."""
    with _client() as c:
        resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers=_headers(),
            params={
                "is_summarized": "eq.false",
                "order": "collected_at.desc",
                "select": "*",
                "limit": str(limit),
            },
        )
        resp.raise_for_status()
        return [ArticleRow.from_dict(row) for row in resp.json()]


def update_summary(article_id: int, summary_ko: Optional[str]) -> bool:
    with _client() as c:
        resp = c.patch(
            f"{_base_url()}/{TABLE}",
            headers=_service_headers(),
            params={"id": f"eq.{article_id}"},
            json={"summary_ko": summary_ko, "is_summarized": True},
        )
        resp.raise_for_status()
        return True


def get_available_dates(limit: int = 30) -> List[str]:
    with _client() as c:
        resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers=_headers(),
            params={
                "select": "collected_at",
                "order": "collected_at.desc",
                "limit": str(limit * 50),
            },
        )
        resp.raise_for_status()

    kst_offset = timedelta(hours=9)
    seen: set = set()
    dates: List[str] = []

    for row in resp.json():
        dt_utc = _parse_dt(row.get("collected_at"))
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
    with _client() as c:
        total_resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers={**_headers(), "Prefer": "count=exact"},
            params={"select": "id", "limit": "1"},
        )
        total_resp.raise_for_status()
        total = int(total_resp.headers.get("content-range", "0/0").split("/")[-1])

        summarized_resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers={**_headers(), "Prefer": "count=exact"},
            params={"select": "id", "summary_ko": "not.is.null", "limit": "1"},
        )
        summarized_resp.raise_for_status()
        summarized = int(summarized_resp.headers.get("content-range", "0/0").split("/")[-1])

        sources_resp = c.get(
            f"{_base_url()}/{TABLE}",
            headers=_headers(),
            params={"select": "source_name"},
        )
        sources_resp.raise_for_status()

    source_counts: dict = {}
    for row in sources_resp.json():
        name = row["source_name"]
        source_counts[name] = source_counts.get(name, 0) + 1

    return {
        "total_articles": total,
        "summarized": summarized,
        "unsummarized": total - summarized,
        "sources": [{"name": k, "count": v} for k, v in source_counts.items()],
    }


def get_client():
    """디버그 엔드포인트 호환용 — 직접 테스트 쿼리 실행."""
    class _FakeClient:
        def table(self, name):
            return self
        def select(self, *a, **kw):
            return self
        def limit(self, n):
            return self
        def execute(self):
            # 실제 연결 테스트
            with _client() as c:
                resp = c.get(
                    f"{_base_url()}/{TABLE}",
                    headers=_headers(),
                    params={"select": "id", "limit": "1"},
                )
                resp.raise_for_status()
                return type("R", (), {"data": resp.json()})()
    return _FakeClient()
