# FastAPI 애플리케이션 진입점
# Supabase 연동, 스케줄러 시작/종료, 라우터 등록을 담당한다.
# 실행: uvicorn app.main:app --reload

import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

# 로깅 설정 — 앱 시작 전에 먼저 구성
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

import app.supabase_db as supabase_db
from app.briefing import available_dates as briefing_available_dates, load_briefing
from app.scheduler import is_collecting, run_collection_now, start_scheduler, stop_scheduler

# 템플릿 및 정적 파일 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI 뉴스레터 서버 시작 중...")
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"스케줄러 시작 건너뜀 (serverless 환경): {e}")
    logger.info("서버 시작 완료")

    yield

    logger.info("서버 종료 중...")
    stop_scheduler()
    logger.info("서버 종료 완료")


# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="AI 뉴스레터",
    description="매일 아침 국내외 주요 AI 뉴스를 자동 수집하여 한국어로 요약 제공",
    version="2.0.0",
    lifespan=lifespan,
)

# 보안 헤더 미들웨어
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 정적 파일 마운트 (로컬 개발 환경에서만 사용, Vercel은 CDN에서 직접 서빙)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 템플릿 엔진 설정
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────

def _parse_date_param(date_str: Optional[str]) -> date:
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


# ─────────────────────────────────────────────
# 웹 UI 라우터 (HTML)
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, summary="오늘의 AI 뉴스 홈")
async def home(
    request: Request,
    date: Optional[str] = None,
):
    target_date = _parse_date_param(date)
    articles = supabase_db.get_articles_by_date(target_date)
    # Instinct 브리핑 카드는 전용 페이지(/instinct-briefing)에서만 보이도록 홈에서는 제외
    articles = [a for a in articles if a.source_name != supabase_db.BRIEFING_SOURCE_NAME]
    available_dates = supabase_db.get_available_dates()

    today_str = datetime.today().strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "articles": articles,
            "selected_date": target_date.isoformat(),
            "today": today_str,
            "available_dates": available_dates,
            "article_count": len(articles),
        },
    )


@app.get("/news", response_class=HTMLResponse, summary="날짜별 뉴스 아카이브")
async def news_archive(
    request: Request,
    date: Optional[str] = None,
):
    target_date = _parse_date_param(date)
    articles = supabase_db.get_articles_by_date(target_date)
    # 홈과 마찬가지로 Instinct 브리핑 카드는 아카이브에서도 제외 (전용 페이지에서만 표시)
    articles = [a for a in articles if a.source_name != supabase_db.BRIEFING_SOURCE_NAME]
    available_dates = supabase_db.get_available_dates()

    return templates.TemplateResponse(
        "news.html",
        {
            "request": request,
            "articles": articles,
            "selected_date": target_date.isoformat(),
            "available_dates": available_dates,
            "article_count": len(articles),
        },
    )


@app.get("/instinct-briefing", response_class=HTMLResponse, summary="Instinct 브리핑")
async def instinct_briefing(request: Request):
    """POST /api/briefing으로 적재된 Instinct 브리핑 항목을 최신순 카드로 보여준다."""
    articles = supabase_db.get_briefing_items()
    return templates.TemplateResponse(
        "instinct_briefing.html",
        {
            "request": request,
            "articles": articles,
            "article_count": len(articles),
        },
    )


@app.get("/briefing", response_class=HTMLResponse, summary="모닝 브리핑 (AI·주식 / 부동산 / 경제방송 / 링크드인)")
async def morning_briefing(
    request: Request,
    date: Optional[str] = None,
):
    """저장소의 data/briefings/YYYY-MM-DD.json 을 읽어 모닝 브리핑 페이지를 렌더링한다."""
    dates = briefing_available_dates()

    selected = None
    if date:
        try:
            selected = datetime.strptime(date, "%Y-%m-%d").date().isoformat()
        except ValueError:
            selected = None

    # 요청 날짜에 브리핑이 없으면 가장 최신 브리핑으로 대체
    if selected not in dates:
        selected = dates[0] if dates else None

    briefing = load_briefing(selected) if selected else None

    newer_date = None
    older_date = None
    if selected and selected in dates:
        idx = dates.index(selected)
        newer_date = dates[idx - 1] if idx > 0 else None
        older_date = dates[idx + 1] if idx + 1 < len(dates) else None

    return templates.TemplateResponse(
        "briefing.html",
        {
            "request": request,
            "briefing": briefing,
            "selected_date": selected or "",
            "available_dates": dates,
            "newer_date": newer_date,
            "older_date": older_date,
            # 날짜 선택기 max 값 — Vercel(UTC)에서도 한국 날짜 기준으로 계산한다
            "today": (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d"),
        },
    )


# ─────────────────────────────────────────────
# REST API 라우터 (JSON)
# ─────────────────────────────────────────────

@app.get("/health", summary="서버 헬스체크")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/debug", summary="배포 환경 디버그")
async def debug_info():
    """Vercel 배포 환경 진단용 엔드포인트."""
    db_test = None
    db_error = None
    try:
        client = supabase_db.get_client()
        result = client.table("ainewsletter_items").select("id").limit(1).execute()
        db_test = f"OK (rows: {len(result.data)})"
    except Exception as e:
        db_error = f"{type(e).__name__}: {str(e)[:300]}"

    return {
        "base_dir": BASE_DIR,
        "templates_dir_exists": os.path.isdir(TEMPLATES_DIR),
        "static_dir_exists": os.path.isdir(STATIC_DIR),
        "supabase_url_set": bool(os.getenv("SUPABASE_URL")),
        "supabase_key_set": bool(os.getenv("SUPABASE_ANON_KEY")),
        "openrouter_key_set": bool(os.getenv("OPENROUTER_API_KEY")),
        "db_test": db_test,
        "db_error": db_error,
    }


@app.get("/api/articles", summary="기사 목록 조회 (JSON)")
async def get_articles(date: Optional[str] = None):
    target_date = _parse_date_param(date)
    articles = supabase_db.get_articles_by_date(target_date)

    return {
        "date": target_date.isoformat(),
        "total": len(articles),
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "source_name": a.source_name,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "collected_at": a.collected_at.isoformat() if a.collected_at else None,
                "summary_ko": a.summary_ko,
                "is_summarized": a.is_summarized,
            }
            for a in articles
        ],
    }


@app.post("/api/collect", summary="뉴스 수집 수동 트리거")
async def trigger_collection():
    if is_collecting():
        raise HTTPException(
            status_code=409,
            detail="이미 수집이 진행 중입니다. 완료 후 다시 시도하세요.",
        )

    from app.scheduler import _async_collection_pipeline

    try:
        result = await _async_collection_pipeline()
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"수집 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



def _verify_cron_secret(request: Request):
    """Vercel Cron Secret 인증 헬퍼. CRON_SECRET 환경변수가 설정된 경우 검증한다."""
    cron_secret = os.getenv("CRON_SECRET", "")
    if cron_secret:
        auth_header = request.headers.get("authorization", "")
        if auth_header != f"Bearer {cron_secret}":
            raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/cron/collect", summary="Vercel Cron — 매일 오전 7시(KST) RSS 수집")
async def cron_collect(request: Request):
    """Vercel Cron Job에서 호출 (UTC 22:00 = KST 07:00). RSS 수집만 실행한다."""
    _verify_cron_secret(request)

    import asyncio
    from app.crawler import fetch_all_feeds

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fetch_all_feeds)
        logger.info(f"크론 수집 완료: {result}")
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"크론 수집 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/stats", summary="수집 통계 조회")
async def get_stats():
    return supabase_db.get_stats()


@app.post("/api/scrap", summary="기사 스크랩 요청 (큐 추가)")
async def scrap_article(request: Request):
    """기사를 스크랩 상태로 마킹하고 Obsidian 저장 큐에 추가한다."""
    data = await request.json()
    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()
    source_name = (data.get("source_name") or "").strip()

    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="유효하지 않은 URL입니다")

    try:
        # 원문 전문이 저장된 항목(Instinct 브리핑 등)은 큐에 함께 실어 보낸다.
        # full_text 컬럼 마이그레이션 전이라도 스크랩은 동작해야 하므로 조회 실패는 무시한다.
        try:
            full_text = supabase_db.get_article_full_text(url)
        except Exception:
            full_text = None
        supabase_db.mark_article_scrapped(url)
        queue_id = supabase_db.enqueue_scrap(url, title, source_name, content=full_text)
        return {
            "status": "ok",
            "queued": queue_id is not None,
            "message": "스크랩이 예약되었습니다. MacBook이 켜져 있으면 곧 Obsidian에 저장됩니다.",
        }
    except Exception as e:
        logger.error(f"스크랩 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scrap/pending", summary="미처리 스크랩 큐 조회 (에이전트용)")
async def get_pending_scraps(request: Request):
    """obsidian_agent가 폴링하는 엔드포인트."""
    _verify_cron_secret(request)
    items = supabase_db.get_pending_scraps()
    return {"items": items}


@app.post("/api/scrap/done", summary="스크랩 처리 완료 보고 (에이전트용)")
async def mark_scrap_done(request: Request):
    """obsidian_agent가 처리 완료 후 호출."""
    _verify_cron_secret(request)
    data = await request.json()
    queue_id = data.get("id")
    success = data.get("success", True)
    error_message = data.get("error_message")

    if not queue_id:
        raise HTTPException(status_code=400, detail="id 필수")

    supabase_db.complete_scrap(queue_id, success, error_message)
    return {"status": "ok"}


@app.post("/api/briefing", summary="Instinct 아침 브리핑 항목 추가 (에이전트용)")
async def add_briefing(request: Request):
    """Instinct 에이전트가 생성한 아침 브리핑 항목을 기사로 적재한다.

    body: {
        "date": "2026-11-21",           # 선택(참고용)
        "items": [
            {"title": str, "url": str, "summary": str, "fulltext": str?},
            ...
        ]
    }
    항목은 source_name="Instinct 브리핑"으로 저장되어 홈/아카이브 카드에 자연스럽게 표시된다.
    """
    _verify_cron_secret(request)
    data = await request.json()
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="items 배열이 필요합니다")
    if len(items) > 100:
        raise HTTPException(status_code=400, detail="items는 한 번에 최대 100개까지 가능합니다")

    inserted = 0
    skipped: list = []
    errors: list = []
    for raw in items:
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        summary = (raw.get("summary") or "").strip()
        fulltext = (raw.get("fulltext") or "").strip() or None
        if not title or not (url.startswith("http://") or url.startswith("https://")):
            skipped.append(url or title or "(제목 없음)")
            continue
        try:
            if supabase_db.url_exists(url):
                skipped.append(url)
                continue
            row = supabase_db.save_briefing_item(
                title=title,
                url=url,
                summary=summary,
                full_text=fulltext,
                source_url=data.get("source_url"),
            )
            if row:
                inserted += 1
        except Exception as e:
            logger.error(f"브리핑 항목 저장 실패: {url} — {e}")
            errors.append(url)

    return {"status": "ok", "inserted": inserted, "skipped": skipped, "errors": errors}
