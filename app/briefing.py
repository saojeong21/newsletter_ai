# 모닝 브리핑 데이터 로더
# 저장소의 data/briefings/YYYY-MM-DD.json 파일을 읽어 /briefing 화면에 필요한 형태로 변환한다.
# 매일 아침 10시 브리핑 JSON을 커밋·푸시하면 Vercel 자동 배포로 화면이 갱신된다.

import json
import logging
import os
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(APP_DIR)

# Vercel 서버리스 번들에서는 includeFiles 경로에 따라 위치가 달라질 수 있어 두 곳을 모두 확인한다.
BRIEFING_DIRS = (
    os.path.join(REPO_DIR, "data", "briefings"),
    os.path.join(APP_DIR, "data", "briefings"),
)

# 브리핑 4개 섹션의 기본 정의 (JSON에 key만 있으면 나머지는 여기 값을 쓴다)
SECTION_DEFAULTS = [
    {"key": "ai_stock", "no": 1, "title": "AI·주식", "icon": "📈", "color": "#6366f1"},
    {"key": "realestate", "no": 2, "title": "국내 부동산", "icon": "🏠", "color": "#10b981"},
    {"key": "broadcast", "no": 3, "title": "삼프로TV·경제방송", "icon": "🎬", "color": "#f59e0b"},
    {"key": "linkedin", "no": 4, "title": "링크드인 AI 피드", "icon": "💼", "color": "#0ea5e9"},
]

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def briefing_dir() -> Optional[str]:
    """브리핑 JSON 디렉터리 경로. 없으면 None."""
    for path in BRIEFING_DIRS:
        if os.path.isdir(path):
            return path
    return None


def available_dates() -> List[str]:
    """브리핑이 있는 날짜 목록 (최신순)."""
    directory = briefing_dir()
    if not directory:
        return []

    dates: List[str] = []
    try:
        names = os.listdir(directory)
    except OSError as e:
        logger.error(f"브리핑 디렉터리 읽기 실패: {e}")
        return []

    for name in names:
        if not name.endswith(".json"):
            continue
        stem = name[:-5]
        try:
            datetime.strptime(stem, "%Y-%m-%d")
        except ValueError:
            continue
        dates.append(stem)

    return sorted(dates, reverse=True)


def latest_date() -> Optional[str]:
    dates = available_dates()
    return dates[0] if dates else None


def _format_time(published_at: str, briefing_date: str) -> str:
    """게시 시각 표시값. 브리핑 날짜와 같은 날이면 HH:MM, 아니면 MM/DD HH:MM."""
    if not published_at:
        return ""
    try:
        dt = datetime.fromisoformat(published_at)
    except ValueError:
        return published_at
    if dt.date().isoformat() == briefing_date:
        return dt.strftime("%H:%M")
    return dt.strftime("%m/%d %H:%M")


def _date_label(day: str) -> str:
    try:
        dt = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return day
    return f"{dt.year}년 {dt.month}월 {dt.day}일 ({WEEKDAYS_KO[dt.weekday()]})"


def _normalize_item(raw: dict, section_key: str, briefing_date: str, index: int) -> dict:
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    published_at = raw.get("published_at") or ""
    return {
        "id": raw.get("id") or f"{briefing_date}-{section_key}-{index + 1}",
        "section_key": section_key,
        "title": raw.get("title", ""),
        "url": raw.get("url", ""),
        "source_name": raw.get("source_name", ""),
        "author": raw.get("author", ""),
        "summary": raw.get("summary", ""),
        "tags": tags,
        "note": raw.get("note", ""),
        "highlight": bool(raw.get("highlight")),
        "datetime_attr": published_at,
        "time_label": raw.get("posted_label") or _format_time(published_at, briefing_date),
    }


def _build_section(definition: dict, raw: dict, briefing_date: str) -> dict:
    items = [
        _normalize_item(item, definition["key"], briefing_date, i)
        for i, item in enumerate(raw.get("items") or [])
    ]
    return {
        **definition,
        "title": raw.get("title") or definition["title"],
        "icon": raw.get("icon") or definition["icon"],
        "color": raw.get("color") or definition["color"],
        "lead": raw.get("lead", ""),
        "cards": items,
        "count": len(items),
    }


def build_view(data: dict) -> dict:
    """JSON 원본을 화면 렌더링용 구조로 변환한다."""
    briefing_date = data.get("date") or ""
    raw_sections = data.get("sections") or []
    by_key = {s.get("key"): s for s in raw_sections}

    sections = [
        _build_section(default, by_key.pop(default["key"], {}), briefing_date)
        for default in SECTION_DEFAULTS
    ]

    # JSON에 정의된 추가 섹션이 있으면 뒤에 붙인다 (4개 고정이지만 확장 여지 유지)
    extra_no = len(SECTION_DEFAULTS)
    for raw in raw_sections:
        key = raw.get("key")
        if not key or key not in by_key:
            continue
        extra_no += 1
        definition = {
            "key": key,
            "no": raw.get("no", extra_no),
            "title": raw.get("title", key),
            "icon": raw.get("icon", "•"),
            "color": raw.get("color", "#6b7280"),
        }
        sections.append(_build_section(definition, raw, briefing_date))

    total = sum(s["count"] for s in sections)
    highlights = sum(1 for s in sections for item in s["cards"] if item["highlight"])
    filled = sum(1 for s in sections if s["count"] > 0)

    return {
        "date": briefing_date,
        "date_label": _date_label(briefing_date),
        "headline": data.get("headline", ""),
        "coverage": data.get("coverage", ""),
        "edition": data.get("edition", ""),
        "notes": data.get("notes") or [],
        "generated_at": data.get("generated_at", ""),
        "sections": sections,
        "total": total,
        "highlight_count": highlights,
        "section_count": filled,
    }


def load_briefing(day: str) -> Optional[dict]:
    """지정 날짜의 브리핑을 읽어 화면용 구조로 반환한다. 없으면 None."""
    directory = briefing_dir()
    if not directory or not day:
        return None

    path = os.path.join(directory, f"{day}.json")
    if not os.path.isfile(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"브리핑 파일 읽기 실패 ({path}): {e}")
        return None

    if not isinstance(data, dict):
        logger.error(f"브리핑 파일 형식 오류 ({path}): 최상위가 객체가 아닙니다")
        return None

    data.setdefault("date", day)
    return build_view(data)
