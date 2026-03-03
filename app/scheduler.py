import asyncio
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as pytz_timezone

logger = logging.getLogger(__name__)

_collection_lock = threading.Lock()
_is_collecting = False
_scheduler: BackgroundScheduler = None


def _run_collection_job():
    global _is_collecting
    with _collection_lock:
        if _is_collecting:
            logger.warning("이미 수집 중입니다. 중복 실행 방지로 건너뜀.")
            return
        _is_collecting = True
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_async_collection_pipeline())
            logger.info(f"스케줄 수집 완료: {result}")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"스케줄 수집 중 오류 발생: {e}", exc_info=True)
    finally:
        with _collection_lock:
            _is_collecting = False


async def _async_collection_pipeline() -> dict:
    from app.crawler import fetch_all_feeds
    from app.database import SessionLocal
    from app.summarizer import summarize_unsummarized_articles

    db = SessionLocal()
    try:
        crawl_result = fetch_all_feeds(db)
        summary_result = await summarize_unsummarized_articles(db)
        return {"crawl": crawl_result, "summary": summary_result}
    except Exception as e:
        logger.error(f"파이프라인 실행 오류: {e}", exc_info=True)
        raise
    finally:
        db.close()


def run_collection_now() -> dict:
    global _is_collecting
    with _collection_lock:
        if _is_collecting:
            raise RuntimeError("이미 수집이 진행 중입니다.")
        _is_collecting = True
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_async_collection_pipeline())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"수동 수집 오류: {e}", exc_info=True)
        raise
    finally:
        with _collection_lock:
            _is_collecting = False


def is_collecting() -> bool:
    return _is_collecting


def start_scheduler():
    global _scheduler
    kst = pytz_timezone("Asia/Seoul")
    _scheduler = BackgroundScheduler(timezone=kst)
    _scheduler.add_job(
        func=_run_collection_job,
        trigger=CronTrigger(hour=7, minute=0, timezone=kst),
        id="daily_news_collection",
        name="매일 오전 7시 AI 뉴스 수집",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.start()
    logger.info("스케줄러 시작 완료 — 매일 오전 7:00 KST 실행 예정")
    for job in _scheduler.get_jobs():
        logger.info(f"등록된 작업: {job.name} | 다음 실행: {job.next_run_time}")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("스케줄러 종료 완료")
