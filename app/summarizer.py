import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models import Article

load_dotenv()
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

FREE_MODELS = [
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "upstage/solar-pro-3:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-12b-it:free",
    "openai/gpt-oss-20b:free",
]

REQUEST_DELAY_SECONDS = 1.5
API_TIMEOUT_SECONDS = 30

SUMMARY_PROMPT_TEMPLATE = """다음 뉴스 기사를 한국어로 간결하게 요약해주세요. 핵심 내용만 150~200자로 작성하세요.

제목: {title}
내용: {content}

요약:"""


async def _call_openrouter(title, content, model, client):
    prompt = SUMMARY_PROMPT_TEMPLATE.format(title=title, content=content[:1500])
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-newsletter.local",
        "X-Title": "AI Newsletter",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.3,
    }
    response = await client.post(OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=API_TIMEOUT_SECONDS)

    if response.status_code == 429 or response.status_code >= 500:
        response.raise_for_status()
    if response.status_code != 200:
        response.raise_for_status()

    data = response.json()
    if "error" in data:
        err_code = data["error"].get("code", "unknown")
        err_msg = data["error"].get("message", "")
        if err_code == 429 or "rate" in err_msg.lower():
            raise httpx.HTTPStatusError(message=err_msg, request=response.request, response=response)
        return None

    try:
        summary = data["choices"][0]["message"]["content"].strip()
        return summary if summary else None
    except (KeyError, IndexError):
        return None


async def summarize_article(title, content, article_id=None):
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY가 설정되지 않았습니다.")
        return None

    log_prefix = f"[Article #{article_id}]" if article_id else "[Article]"

    async with httpx.AsyncClient() as client:
        for i, model in enumerate(FREE_MODELS):
            try:
                logger.info(f"{log_prefix} 요약 시도: {model} ({i+1}/{len(FREE_MODELS)})")
                summary = await _call_openrouter(title, content, model, client)
                if summary:
                    logger.info(f"{log_prefix} 요약 성공 [{model}]: {len(summary)}자")
                    return summary
            except httpx.HTTPStatusError:
                if i < len(FREE_MODELS) - 1:
                    await asyncio.sleep(1)
                continue
            except (httpx.TimeoutException, Exception) as e:
                logger.warning(f"{log_prefix} [{model}] 오류: {e}")
                continue

    logger.error(f"{log_prefix} 모든 모델에서 요약 실패")
    return None


async def summarize_unsummarized_articles(db: Session) -> dict:
    start_time = time.time()
    articles = db.query(Article).filter(Article.is_summarized == False).order_by(Article.collected_at.desc()).all()  # noqa: E712

    total = len(articles)
    success_count = fail_count = 0
    logger.info(f"요약 대상 기사: {total}건")

    for idx, article in enumerate(articles, 1):
        content = article.description or article.title
        summary = await summarize_article(title=article.title, content=content, article_id=article.id)

        try:
            article.summary_ko = summary
            article.is_summarized = True
            db.commit()
            if summary:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"[Article #{article.id}] DB 업데이트 실패: {e}")
            fail_count += 1

        if idx < total:
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

    duration = time.time() - start_time
    logger.info(f"요약 완료 — 성공: {success_count}, 실패: {fail_count}, 소요시간: {duration:.1f}초")
    return {"total": total, "summarized": success_count, "failed": fail_count, "duration_seconds": round(duration, 2)}
