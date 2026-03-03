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
    """FastAPI 앱 생명주기 관리.

    startup: 스케줄러 시작
    shutdown: 스케줄러 종료
    """
    logger.info("AI 뉴스레터 서버 시작 중...")
    start_scheduler()
    logger.info("서버 시작 완료")

    yield  # 앱 실행 중

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

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 템플릿 엔진 설정
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────

def _parse_date_param(date_str: Optional[str]) -> date:
    """쿼리 파라미터 date 문자열을 date 객체로 변환한다."""
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
    """오늘의 AI 뉴스를 카드뷰로 표시한다."""
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
    """날짜별 뉴스 아카이브 페이지."""
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
    """서버 상태를 반환한다."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/articles", summary="기사 목록 조회 (JSON)")
async def get_articles(date: Optional[str] = None):
    """날짜별 기사 목록을 JSON으로 반환한다."""
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
    """RSS 수집 파이프라인을 즉시 실행한다."""
    if is_collecting():
        raise HTTPException(
            status_code=409,
            detail="이미 수집이 진행 중입니다. 완료 후 다시 시도하세요.",
        )

    import threading

    result_container = {}
    error_container = {}

    def _run():
        try:
            result_container["result"] = run_collection_now()
        except Exception as e:
            error_container["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": "뉴스 수집이 시작되었습니다. 완료까지 최대 10분 소요됩니다.",
        },
    )


@app.get("/api/stats", summary="수집 통계 조회")
async def get_stats():
    """DB에 저장된 기사 통계를 반환한다."""
    return supabase_db.get_stats()
