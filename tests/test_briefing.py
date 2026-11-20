"""모닝 브리핑 페이지 회귀 테스트.

실행: .venv-test/bin/python -m pytest tests -q
(Supabase는 stub으로 대체하므로 네트워크·자격증명 없이 돈다.)
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.briefing as briefing_mod  # noqa: E402
import app.supabase_db as supabase_db  # noqa: E402
from app.main import app  # noqa: E402

BRIEFING_DATE = "2026-11-20"
DATA_FILE = ROOT / "data" / "briefings" / f"{BRIEFING_DATE}.json"

client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_supabase(monkeypatch):
    """홈/아카이브/API 라우트가 외부 Supabase를 호출하지 않도록 대체한다."""
    monkeypatch.setattr(supabase_db, "get_articles_by_date", lambda target_date: [])
    monkeypatch.setattr(supabase_db, "get_available_dates", lambda limit=30: [])
    monkeypatch.setattr(
        supabase_db,
        "get_stats",
        lambda: {"total_articles": 0, "summarized": 0, "unsummarized": 0, "sources": []},
    )


# ── 기존 화면이 깨지지 않았는지 ──

def test_home_page_ok():
    res = client.get("/")
    assert res.status_code == 200
    assert "AI 뉴스레터" in res.text


def test_news_archive_ok():
    res = client.get("/news")
    assert res.status_code == 200
    assert "뉴스 아카이브" in res.text


def test_api_articles_ok():
    res = client.get("/api/articles")
    assert res.status_code == 200
    body = res.json()
    assert body["date"] and "articles" in body and isinstance(body["total"], int)


def test_health_ok():
    assert client.get("/health").json()["status"] == "ok"


# ── /briefing ──

def test_briefing_default_page_renders():
    res = client.get("/briefing")
    assert res.status_code == 200
    assert "/briefing" in res.text
    assert BRIEFING_DATE in res.text
    assert "피클’s 모닝 브리핑" in res.text


def test_briefing_title_and_nav_use_pickle_brand():
    """화면 제목(<title>·히어로)과 상단 메뉴가 '피클’s 모닝 브리핑'으로 표시된다."""
    html = client.get(f"/briefing?date={BRIEFING_DATE}").text
    assert "2026년 11월 20일 (금) 피클’s 모닝 브리핑" in html
    assert 'class="hero-title" id="briefingTitle"' in html
    assert ">피클’s 모닝 브리핑</a>" in html
    assert "피클’s 모닝 브리핑 · 매일 오전 10시" in html
    assert ">모닝 브리핑</a>" not in html


def test_briefing_explicit_date_renders():
    res = client.get(f"/briefing?date={BRIEFING_DATE}")
    assert res.status_code == 200
    assert "2026년 11월 20일 (금)" in res.text
    assert "<title>2026년 11월 20일 (금) 피클’s 모닝 브리핑 — AI 뉴스레터</title>" in res.text


def test_briefing_unknown_date_falls_back_to_latest():
    res = client.get("/briefing?date=2020-01-01")
    assert res.status_code == 200
    assert BRIEFING_DATE in res.text


def test_briefing_invalid_date_does_not_crash():
    res = client.get("/briefing?date=not-a-date")
    assert res.status_code == 200


def test_briefing_shows_four_sections():
    res = client.get(f"/briefing?date={BRIEFING_DATE}")
    for title in ("AI·주식", "국내 부동산", "삼프로TV·경제방송", "링크드인 AI 피드"):
        assert title in res.text


def test_briefing_cards_have_scrap_button_and_original_link():
    res = client.get(f"/briefing?date={BRIEFING_DATE}")
    html = res.text
    assert 'class="news-card briefing-card' in html
    assert 'class="scrap-btn"' in html
    assert "fetch('/api/scrap'" in html
    assert "원문 보기" in html


def test_nav_has_briefing_link_on_home():
    html = client.get("/").text
    assert 'href="/briefing"' in html


def test_briefing_data_file_is_valid():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    assert data["date"] == BRIEFING_DATE
    keys = [s["key"] for s in data["sections"]]
    # 기본 4섹션은 고정 순서, 그 뒤 추가 섹션(예: jobs 채용 공고)은 허용
    assert keys[:4] == ["ai_stock", "realestate", "broadcast", "linkedin"]

    counts = {s["key"]: len(s["items"]) for s in data["sections"]}
    assert all(count > 0 for count in counts.values())

    for section in data["sections"]:
        for item in section["items"]:
            assert item["title"].strip()
            assert item["url"].startswith("https://")
            assert item["source_name"].strip()
            assert item["summary"].strip()


def test_briefing_loader_normalizes_view():
    view = briefing_mod.load_briefing(BRIEFING_DATE)
    assert view is not None
    assert view["date_label"] == "2026년 11월 20일 (금)"
    assert view["total"] > 0
    assert view["section_count"] >= 4
    first = view["sections"][0]["cards"][0]
    assert first["time_label"]
    briefing_mod.available_dates()
    # 최신 브리핑이 요청 날짜 이후로 넘어가지 않는지
    assert briefing_mod.available_dates()[0] >= BRIEFING_DATE


def test_briefing_latest_date_is_returned():
    assert briefing_mod.latest_date() == briefing_mod.available_dates()[0]


def test_briefing_empty_state_without_data(monkeypatch, tmp_path):
    monkeypatch.setattr(briefing_mod, "BRIEFING_DIRS", (str(tmp_path),))
    res = client.get("/briefing")
    assert res.status_code == 200
    assert "아직 피클’s 모닝 브리핑이 없습니다" in res.text


# ── 스크랩 연동 ──

def test_scrap_endpoint_accepts_briefing_item(monkeypatch):
    calls = {}

    def fake_enqueue(url, title, source_name, content=None):
        calls["url"] = url
        calls["title"] = title
        calls["source_name"] = source_name
        return 42

    monkeypatch.setattr(supabase_db, "mark_article_scrapped", lambda url: False)
    monkeypatch.setattr(supabase_db, "enqueue_scrap", fake_enqueue)
    monkeypatch.setattr(supabase_db, "get_article_full_text", lambda url: None)

    payload = {
        "title": "Darwin, 수학·과학 추론 오픈 모델 세계 1위",
        "url": "https://www.linkedin.com/feed/update/urn:li:groupPost:30900014-7529367880153628673/",
        "source_name": "LinkedIn",
    }
    res = client.post("/api/scrap", json=payload)
    assert res.status_code == 200
    assert res.json()["queued"] is True
    assert calls == payload


def test_scrap_endpoint_rejects_bad_url(monkeypatch):
    monkeypatch.setattr(supabase_db, "mark_article_scrapped", lambda url: False)
    monkeypatch.setattr(supabase_db, "enqueue_scrap", lambda url, title, source, content=None: 1)
    res = client.post("/api/scrap", json={"title": "x", "url": "not-a-url", "source_name": "y"})
    assert res.status_code == 400


# ── obsidian_agent 본문 추출 실패 폴백 ──

def test_obsidian_agent_fallback_note():
    sys.path.insert(0, str(ROOT))
    import obsidian_agent  # noqa: E402

    body = obsidian_agent._fallback_body(
        "테스트 제목", "https://example.com/a", "LinkedIn"
    )
    assert "본문 자동 추출 실패" in body
    assert "https://example.com/a" in body
    assert "LinkedIn" in body


def test_obsidian_scrap_writes_fallback_note_for_login_wall(monkeypatch, tmp_path):
    """본문 추출 실패(링크드인 로그인 벽)에도 에러 없이 기본 노트를 남긴다."""
    sys.path.insert(0, str(ROOT))
    import obsidian_agent  # noqa: E402

    monkeypatch.setattr(obsidian_agent, "OBSIDIAN_BASE_DIR", tmp_path)
    monkeypatch.setattr(obsidian_agent.trafilatura, "fetch_url", lambda url: None)
    monkeypatch.setattr(obsidian_agent, "_summarize_article", lambda *a, **k: None)

    flask_client = obsidian_agent.app.test_client()
    res = flask_client.post(
        "/scrap",
        json={
            "title": "Darwin 오픈 모델 1위",
            "url": "https://www.linkedin.com/feed/update/urn:li:activity:1/",
            "source_name": "LinkedIn",
        },
    )

    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["full_text"] is False

    files = list((tmp_path / "AI Newsletter").glob("*.md"))
    assert len(files) == 1
    note = files[0].read_text(encoding="utf-8")
    assert "Darwin 오픈 모델 1위" in note
    assert "본문 자동 추출 실패" in note
    assert "urn:li:activity:1" in note


def test_obsidian_queue_item_completes_without_full_text(monkeypatch, tmp_path):
    """큐 항목도 본문 추출 실패 시 기본 노트로 완료 처리한다(영구 실패 방지)."""
    sys.path.insert(0, str(ROOT))
    import obsidian_agent  # noqa: E402

    monkeypatch.setattr(obsidian_agent, "OBSIDIAN_BASE_DIR", tmp_path)
    monkeypatch.setattr(obsidian_agent.trafilatura, "fetch_url", lambda url: None)
    monkeypatch.setattr(obsidian_agent, "_summarize_article", lambda *a, **k: None)

    statuses = []
    monkeypatch.setattr(
        obsidian_agent,
        "_update_queue_status",
        lambda queue_id, ok, msg=None: statuses.append((queue_id, ok, msg)),
    )

    obsidian_agent._process_queue_item(
        {
            "id": 7,
            "article_url": "https://www.youtube.com/watch?v=qu5RoRs0beQ",
            "title": "앤트로픽 상장 첫날 17% 상승",
            "source_name": "삼프로TV",
            "created_at": "2026-11-20T01:00:00+00:00",
        }
    )

    assert statuses == [(7, True, None)]
    files = list((tmp_path / "AI Newsletter").glob("*.md"))
    assert files and files[0].name == "26.11.20(Fri).md"
    assert "삼프로TV" in files[0].read_text(encoding="utf-8")


# ── Obsidian 소스별 폴더 라우팅 ──

@pytest.mark.parametrize(
    "source_name, folder",
    [
        ("Instinct 브리핑", "Instinct Briefing"),
        ("피클 브리핑 · 서울경제", "Pickle Briefing"),
        ("AI타임스", "AI Newsletter"),
    ],
)
def test_obsidian_routes_by_source(monkeypatch, tmp_path, source_name, folder):
    import obsidian_agent  # noqa: E402

    monkeypatch.setattr(obsidian_agent, "OBSIDIAN_BASE_DIR", tmp_path)
    from datetime import datetime as _dt

    name = obsidian_agent._write_to_obsidian(
        "제목", "https://example.com/x", source_name, "본문", None, _dt(2026, 11, 20, 1, 0)
    )
    assert name == "26.11.20(Fri).md"
    assert (tmp_path / folder / name).exists()


def test_obsidian_newest_entry_goes_on_top(monkeypatch, tmp_path):
    import obsidian_agent  # noqa: E402

    monkeypatch.setattr(obsidian_agent, "OBSIDIAN_BASE_DIR", tmp_path)
    from datetime import datetime as _dt

    when = _dt(2026, 11, 20, 1, 0)
    obsidian_agent._write_to_obsidian("첫번째", "https://e.com/1", "AI타임스", "a", None, when)
    obsidian_agent._write_to_obsidian("두번째", "https://e.com/2", "AI타임스", "b", None, when)
    note = (tmp_path / "AI Newsletter" / "26.11.20(Fri).md").read_text(encoding="utf-8")
    assert note.startswith("---\ndate: 26.11.20(Fri)")
    assert note.index("두번째") < note.index("첫번째")


# ── mkcert 인증서 해석 (IP 변경 시 크래시 루프 방지) ──

def _touch_pair(directory, ip):
    (directory / f"{ip}+1.pem").write_text("c")
    (directory / f"{ip}+1-key.pem").write_text("k")


def test_ssl_cert_exact_ip(monkeypatch, tmp_path):
    import obsidian_agent  # noqa: E402

    monkeypatch.setattr(obsidian_agent, "MKCERT_DIR", tmp_path)
    _touch_pair(tmp_path, "10.0.0.5")
    cert, key = obsidian_agent._resolve_ssl_cert("10.0.0.5")
    assert cert.name == "10.0.0.5+1.pem" and key.name == "10.0.0.5+1-key.pem"


def test_ssl_cert_falls_back_to_existing_when_mkcert_missing(monkeypatch, tmp_path):
    import obsidian_agent  # noqa: E402
    import shutil

    monkeypatch.setattr(obsidian_agent, "MKCERT_DIR", tmp_path)
    monkeypatch.setattr(obsidian_agent, "_MKCERT_CANDIDATES", ())
    monkeypatch.setattr(shutil, "which", lambda name: None)
    _touch_pair(tmp_path, "192.168.0.10")
    cert, key = obsidian_agent._resolve_ssl_cert("192.168.0.8")
    assert cert.name == "192.168.0.10+1.pem" and key.name == "192.168.0.10+1-key.pem"


def test_ssl_cert_mkcert_succeeds_without_files_falls_back(monkeypatch, tmp_path):
    """mkcert가 0으로 종료했지만 파일을 만들지 않으면 기존 인증서로 대체한다(크래시 루프 방지)."""
    import obsidian_agent  # noqa: E402
    import shutil
    import subprocess

    monkeypatch.setattr(obsidian_agent, "MKCERT_DIR", tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/mkcert")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    _touch_pair(tmp_path, "192.168.0.10")
    cert, _ = obsidian_agent._resolve_ssl_cert("192.168.0.8")
    assert cert.name == "192.168.0.10+1.pem"


def test_ssl_cert_none_when_nothing_available(monkeypatch, tmp_path):
    import obsidian_agent  # noqa: E402
    import shutil

    monkeypatch.setattr(obsidian_agent, "MKCERT_DIR", tmp_path)
    monkeypatch.setattr(obsidian_agent, "_MKCERT_CANDIDATES", ())
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert obsidian_agent._resolve_ssl_cert("192.168.0.8") is None


# ── /instinct-briefing 날짜별 표시 ──

def _briefing_row(title, url, collected_utc, category="AI 뉴스·주식"):
    return supabase_db.ArticleRow(
        id=abs(hash(url)) % 10000, title=title, url=url,
        source_name=supabase_db.BRIEFING_SOURCE_NAME, category=category,
        published_at=collected_utc, collected_at=collected_utc, summary_ko="요약",
    )


@pytest.fixture
def instinct_rows(monkeypatch):
    from datetime import datetime as _dt

    rows = [
        # UTC 2026-11-20 23:30 = KST 11-21 08:30 → 11-21
        _briefing_row("오늘 항목", "https://e.com/today", _dt(2026, 11, 20, 23, 30)),
        # UTC 2026-11-20 00:30 = KST 11-20 09:30 → 11-20
        _briefing_row("어제 항목", "https://e.com/yday", _dt(2026, 11, 20, 0, 30)),
    ]
    from datetime import timedelta as _td

    def _day(r):
        return (r.collected_at + _td(hours=9)).date().isoformat()

    monkeypatch.setattr(
        supabase_db, "get_briefing_dates", lambda limit=5000: sorted({_day(r) for r in rows}, reverse=True)
    )
    monkeypatch.setattr(
        supabase_db, "get_briefing_items_for_day", lambda day, limit=500: [r for r in rows if _day(r) == day]
    )
    return rows


def test_instinct_briefing_defaults_to_latest_kst_day(instinct_rows):
    html = client.get("/instinct-briefing").text
    assert "2026년 11월 21일 토요일" in html
    assert "오늘 항목" in html and "어제 항목" not in html
    assert 'href="/instinct-briefing?date=2026-11-20"' in html


def test_instinct_briefing_date_param_filters(instinct_rows):
    html = client.get("/instinct-briefing?date=2026-11-20").text
    assert "2026년 11월 20일 금요일" in html
    assert "어제 항목" in html and "오늘 항목" not in html


def test_instinct_briefing_unknown_date_falls_back(instinct_rows):
    html = client.get("/instinct-briefing?date=1999-01-01").text
    assert "오늘 항목" in html


def test_instinct_briefing_empty(monkeypatch):
    monkeypatch.setattr(supabase_db, "get_briefing_dates", lambda limit=5000: [])
    monkeypatch.setattr(supabase_db, "get_briefing_items_for_day", lambda day, limit=500: [])
    res = client.get("/instinct-briefing")
    assert res.status_code == 200
    assert "아직 적재된 브리핑 항목이 없습니다" in res.text


# ── Supabase 타임스탬프 파싱 (Python 3.9: 소수점 5자리 등) ──

@pytest.mark.parametrize(
    "raw",
    ["2026-11-20T09:30:51.08673+00:00", "2026-11-20T09:30:51.1+00:00", "2026-11-20T09:30:51Z",
     "2026-11-20T09:30:51.123456789+00:00"],
)
def test_parse_dt_handles_supabase_fraction_digits(raw):
    dt = supabase_db._parse_dt(raw)
    assert dt is not None and (dt.hour, dt.minute, dt.second) == (9, 30, 51)


def test_agent_queue_uses_created_at_with_5_digit_fraction(monkeypatch, tmp_path):
    import obsidian_agent  # noqa: E402

    monkeypatch.setattr(obsidian_agent, "OBSIDIAN_BASE_DIR", tmp_path)
    monkeypatch.setattr(obsidian_agent, "_extract_content", lambda url: None)
    monkeypatch.setattr(obsidian_agent, "_update_queue_status", lambda *a, **k: None)
    obsidian_agent._process_queue_item({
        "id": 1, "article_url": "https://e.com/x", "title": "t", "source_name": "AI타임스",
        # UTC 11-19 20:00 → KST 11-20 05:00
        "created_at": "2026-11-19T20:00:00.08673+00:00",
    })
    assert (tmp_path / "AI Newsletter" / "26.11.20(Fri).md").exists()
