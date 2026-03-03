import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

from app.database import get_db, init_db
from app.models import Article
from app.scheduler import is_collecting, run_collection_now, start_scheduler, stop_scheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI 뉴스레터 서버 시작 중...")
    init_db()
    start_scheduler()
    logger.info("서버 시작 완료")
    yield
    logger.info("서버 종료 중...")
    stop_scheduler()
    logger.info("서버 종료 완료")


app = FastAPI(
    title="AI 뉴스레터",
    description="매일 아침 국내외 주요 AI 뉴스를 자동 수집하여 한국어로 요약 제공",
    version="1.0.0",
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _get_articles_by_date(db: Session, target_date: date) -> list:
    kst_offset = timedelta(hours=9)
    start_utc = datetime.combine(target_date, datetime.min.time()) - kst_offset
    end_utc = start_utc + timedelta(days=1)
    return (
        db.query(Article)
        .filter(Article.collected_at >= start_utc, Article.collected_at < end_utc)
        .order_by(Article.collected_at.desc())
        .all()
    )


def _parse_date_param(date_str: Optional[str]) -> date:
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def _get_available_dates(db: Session, limit: int = 30) -> list:
    rows = (
        db.query(func.date(func.datetime(Article.collected_at, "+9 hours")).label("d"))
        .group_by(func.date(func.datetime(Article.collected_at, "+9 hours")))
        .order_by(func.date(func.datetime(Article.collected_at, "+9 hours")).desc())
        .limit(limit)
        .all()
    )
    return [row.d for row in rows]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, date: Optional[str] = None, db: Session = Depends(get_db)):
    target_date = _parse_date_param(date)
    articles = _get_articles_by_date(db, target_date)
    available_dates = _get_available_dates(db)
    return templates.TemplateResponse("index.html", {
        "request": request, "articles": articles,
        "selected_date": target_date.isoformat(), "today": datetime.today().strftime("%Y-%m-%d"),
        "available_dates": available_dates, "article_count": len(articles),
    })


@app.get("/news", response_class=HTMLResponse)
async def news_archive(request: Request, date: Optional[str] = None, db: Session = Depends(get_db)):
    target_date = _parse_date_param(date)
    articles = _get_articles_by_date(db, target_date)
    available_dates = _get_available_dates(db)
    return templates.TemplateResponse("news.html", {
        "request": request, "articles": articles,
        "selected_date": target_date.isoformat(),
        "available_dates": available_dates, "article_count": len(articles),
    })


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/articles")
async def get_articles(date: Optional[str] = None, db: Session = Depends(get_db)):
    target_date = _parse_date_param(date)
    articles = _get_articles_by_date(db, target_date)
    return {
        "date": target_date.isoformat(), "total": len(articles),
        "articles": [{
            "id": a.id, "title": a.title, "url": a.url, "source_name": a.source_name,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "collected_at": a.collected_at.isoformat() if a.collected_at else None,
            "summary_ko": a.summary_ko, "is_summarized": a.is_summarized,
        } for a in articles],
    }


@app.post("/api/collect")
async def trigger_collection():
    if is_collecting():
        raise HTTPException(status_code=409, detail="이미 수집이 진행 중입니다. 완료 후 다시 시도하세요.")

    import threading
    def _run():
        try:
            run_collection_now()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse(status_code=202, content={"status": "accepted", "message": "뉴스 수집이 시작되었습니다. 완료까지 최대 10분 소요됩니다."})


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    total_articles = db.query(func.count(Article.id)).scalar()
    summarized = db.query(func.count(Article.id)).filter(Article.summary_ko.isnot(None)).scalar()
    sources = db.query(Article.source_name, func.count(Article.id).label("count")).group_by(Article.source_name).all()
    return {
        "total_articles": total_articles, "summarized": summarized,
        "unsummarized": total_articles - summarized,
        "sources": [{"name": s.source_name, "count": s.count} for s in sources],
    }
