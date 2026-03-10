# FastAPI 애플리케이션 진입점
# Supabase 연동, 스케줄러 시작/종료, 라우터 등록을 담당한다.
# 실행: uvicorn app.main:app --reload

import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
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


@app.post("/api/summarize", summary="AI 요약 수동 트리거")
@app.get("/api/summarize", summary="AI 요약 수동 트리거 (GET — Vercel Cron용)")
async def trigger_summarization(limit: int = 10):
    """미요약 기사에 대한 AI 요약을 생성한다. limit으로 처리 건수 제한 (기본 10)."""
    from app.summarizer import summarize_unsummarized_articles

    try:
        result = await summarize_unsummarized_articles(limit=limit)
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"요약 오류: {e}", exc_info=True)
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
    """Vercel Cron Job에서 호출 (UTC 22:00 = KST 07:00). RSS 수집만 실행한다.

    Hobby 플랜 60초 제한 내 완료되도록 수집 단독 실행.
    요약은 20분 후 /api/cron/summarize가 별도로 처리한다.
    """
    _verify_cron_secret(request)

    import asyncio
    from app.crawler import fetch_all_feeds

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, fetch_all_feeds)
        logger.info(f"크론 수집 완료: {result}")
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"크론 수집 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cron/summarize", summary="Vercel Cron — 매일 오전 7시 20분(KST) AI 요약")
async def cron_summarize(request: Request):
    """Vercel Cron Job에서 호출 (UTC 22:20 = KST 07:20). 미요약 기사 AI 요약 실행.

    Hobby 플랜 60초 제한: limit=5로 제한.
    기사당 평균 10초 × 5건 + 딜레이 4 × 2초 = ~58초 (60초 이내 안전).
    누적 미요약 기사는 매일 5건씩 자동 처리된다.
    """
    _verify_cron_secret(request)

    from app.summarizer import summarize_unsummarized_articles

    try:
        result = await summarize_unsummarized_articles(limit=5)
        logger.info(f"크론 요약 완료: {result}")
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"크론 요약 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", summary="수집 통계 조회")
async def get_stats():
    return supabase_db.get_stats()
