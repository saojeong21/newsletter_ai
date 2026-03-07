# APScheduler 기반 자동 수집 스케줄러
# 매일 오전 7시(KST = UTC+9)에 RSS 수집 및 AI 요약을 자동 실행한다.
# FastAPI lifespan 이벤트에서 시작/종료한다.

import asyncio
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as pytz_timezone

logger = logging.getLogger(__name__)

# 수집 작업 중복 실행 방지용 Lock
_collection_lock = threading.Lock()
_is_collecting = False

# 전역 스케줄러 인스턴스
_scheduler: BackgroundScheduler = None


def _run_collection_job():
    """스케줄러에서 호출되는 동기 래퍼 함수.

    비동기 수집 파이프라인을 새 이벤트 루프에서 실행한다.
    동시 실행 방지를 위해 Lock을 사용한다.
    """
    global _is_collecting

    with _collection_lock:
        if _is_collecting:
            logger.warning("이미 수집 중입니다. 중복 실행 방지로 건너뜀.")
            return
        _is_collecting = True

    try:
        logger.info("스케줄된 뉴스 수집 시작")
        # 새 이벤트 루프 생성 (BackgroundScheduler는 별도 스레드에서 실행)
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
    """RSS 수집 → AI 요약의 전체 파이프라인을 실행한다.

    Returns:
        dict: 수집 및 요약 결과 집계
    """
    import asyncio
    from app.crawler import fetch_all_feeds
    from app.summarizer import summarize_unsummarized_articles

    global _is_collecting
    with _collection_lock:
        _is_collecting = True

    try:
        # 1단계: RSS 피드 수집 (동기 함수를 스레드풀에서 실행)
        logger.info("1단계: RSS 피드 수집 시작")
        loop = asyncio.get_event_loop()
        crawl_result = await loop.run_in_executor(None, fetch_all_feeds)
        logger.info(f"RSS 수집 결과: {crawl_result}")

        # 2단계: AI 요약 생성 (Vercel maxDuration=300초 내 완료 가능하도록 limit 제한)
        logger.info("2단계: AI 요약 생성 시작")
        summary_result = await summarize_unsummarized_articles(limit=20)
        logger.info(f"요약 결과: {summary_result}")
    finally:
        with _collection_lock:
            _is_collecting = False

    return {
        "crawl": crawl_result,
        "summary": summary_result,
    }


def run_collection_now() -> dict:
    """수동으로 수집 파이프라인을 즉시 실행한다.

    이미 수집 중이면 예외를 발생시킨다.
    API 엔드포인트에서 호출하는 동기 진입점이다.

    Returns:
        dict: 수집 결과

    Raises:
        RuntimeError: 이미 수집이 진행 중인 경우
    """
    global _is_collecting

    with _collection_lock:
        if _is_collecting:
            raise RuntimeError("이미 수집이 진행 중입니다.")
        _is_collecting = True

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_async_collection_pipeline())
            return result
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"수동 수집 오류: {e}", exc_info=True)
        raise
    finally:
        with _collection_lock:
            _is_collecting = False


def is_collecting() -> bool:
    """현재 수집 진행 여부를 반환한다."""
    return _is_collecting


def start_scheduler():
    """APScheduler를 시작하고 매일 오전 7시(KST) 수집 작업을 등록한다.

    FastAPI lifespan의 startup 단계에서 호출한다.
    """
    global _scheduler

    kst = pytz_timezone("Asia/Seoul")

    _scheduler = BackgroundScheduler(timezone=kst)

    # 매일 오전 7시 KST 실행
    _scheduler.add_job(
        func=_run_collection_job,
        trigger=CronTrigger(hour=7, minute=0, timezone=kst),
        id="daily_news_collection",
        name="매일 오전 7시 AI 뉴스 수집",
        replace_existing=True,
        misfire_grace_time=300,  # 5분 이내 지연 실행 허용
    )

    _scheduler.start()
    logger.info("스케줄러 시작 완료 — 매일 오전 7:00 KST 실행 예정")

    # 등록된 작업 목록 로그 출력
    for job in _scheduler.get_jobs():
        logger.info(f"등록된 작업: {job.name} | 다음 실행: {job.next_run_time}")


def stop_scheduler():
    """APScheduler를 종료한다.

    FastAPI lifespan의 shutdown 단계에서 호출한다.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("스케줄러 종료 완료")
