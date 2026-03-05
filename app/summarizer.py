# OpenRouter API 연동 AI 요약 모듈
# 무료 모델 우선순위에 따라 순차 폴백(fallback) 로직을 구현한다.
# rate limit(429), 서버 오류(5xx) 발생 시 다음 모델로 자동 전환한다.

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv

import app.supabase_db as supabase_db

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# 무료 모델 우선순위 목록 (OpenRouter 실제 가용 모델 기준, 2026-03 확인)
# rate limit 또는 에러 발생 시 순서대로 다음 모델로 자동 전환.
# 한국어 지원 품질 우수 모델을 상위에 배치.
FREE_MODELS = [
    "openai/gpt-oss-120b:free",                         # OpenAI 오픈소스 120B — 최고 품질
    "meta-llama/llama-3.3-70b-instruct:free",           # Llama 70B — 한국어 우수
    "qwen/qwen3-next-80b-a3b-instruct:free",            # Qwen3 80B — 다국어 강세
    "upstage/solar-pro-3:free",                         # Upstage Solar — 한국어 특화
    "google/gemma-3-27b-it:free",                       # Gemma 27B — 다국어
    "mistralai/mistral-small-3.1-24b-instruct:free",    # Mistral 24B — 유럽어/영어
    "google/gemma-3-12b-it:free",                       # Gemma 12B — 경량 폴백
    "openai/gpt-oss-20b:free",                          # OpenAI 오픈소스 20B
]

# 기사 간 요청 딜레이 (초) — rate limit 회피
REQUEST_DELAY_SECONDS = 1.5

# API 요청 타임아웃 (초)
API_TIMEOUT_SECONDS = 30

# 요약 프롬프트 템플릿
SUMMARY_PROMPT_TEMPLATE = """다음 뉴스 기사를 한국어로 간결하게 요약해주세요. 핵심 내용만 150~200자로 작성하세요.

제목: {title}
내용: {content}

요약:"""


async def _call_openrouter(
    title: str,
    content: str,
    model: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """OpenRouter API를 호출하여 기사 요약을 생성한다.

    Args:
        title: 기사 제목
        content: 기사 본문/설명
        model: 사용할 모델 ID
        client: 재사용할 httpx AsyncClient

    Returns:
        요약 텍스트 (성공 시) 또는 None (실패 시)

    Raises:
        httpx.HTTPStatusError: 429, 5xx 오류 (폴백 트리거용)
    """
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        title=title,
        content=content[:1500],  # 컨텍스트 길이 제한
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-newsletter.local",
        "X-Title": "AI Newsletter",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "max_tokens": 300,
        "temperature": 0.3,
    }

    response = await client.post(
        OPENROUTER_BASE_URL,
        headers=headers,
        json=payload,
        timeout=API_TIMEOUT_SECONDS,
    )

    if response.status_code == 429:
        logger.warning(f"[{model}] Rate limit 초과 (429) — 다음 모델로 전환")
        response.raise_for_status()

    if response.status_code >= 500:
        logger.warning(f"[{model}] 서버 오류 ({response.status_code}) — 다음 모델로 전환")
        response.raise_for_status()

    if response.status_code != 200:
        logger.warning(f"[{model}] 예상치 못한 응답 코드: {response.status_code}")
        response.raise_for_status()

    data = response.json()

    # 200 OK이더라도 에러 응답이 포함될 수 있음 (일부 프로바이더 동작)
    if "error" in data:
        err_code = data["error"].get("code", "unknown")
        err_msg = data["error"].get("message", "")
        if err_code == 429 or "rate" in err_msg.lower():
            logger.warning(f"[{model}] 응답 내 Rate limit 에러 — 다음 모델로 전환")
            # HTTPStatusError처럼 폴백을 위해 예외 발생
            raise httpx.HTTPStatusError(
                message=err_msg,
                request=response.request,
                response=response,
            )
        logger.warning(f"[{model}] 응답 내 에러: code={err_code}, msg={err_msg[:100]}")
        return None

    try:
        summary = data["choices"][0]["message"]["content"].strip()
        if not summary:
            logger.warning(f"[{model}] 빈 응답 반환됨")
            return None
        return summary
    except (KeyError, IndexError) as e:
        logger.error(f"[{model}] 응답 파싱 실패: {e} — 응답: {data}")
        return None


async def summarize_article(
    title: str,
    content: str,
    article_id: Optional[int] = None,
) -> Optional[str]:
    """무료 모델 순차 폴백으로 기사를 한국어 요약한다.

    모든 모델에서 실패하면 None을 반환한다.

    Args:
        title: 기사 제목
        content: 기사 본문/설명
        article_id: 로깅용 기사 ID (선택)

    Returns:
        한국어 요약 텍스트 또는 None
    """
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
                    logger.info(
                        f"{log_prefix} 요약 성공 [{model}]: "
                        f"{len(summary)}자"
                    )
                    return summary
                else:
                    logger.warning(f"{log_prefix} [{model}] 빈 요약, 다음 모델 시도")

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"{log_prefix} [{model}] HTTP 오류 {e.response.status_code}: "
                    f"{e.response.text[:200]}"
                )
                # 폴백: 다음 모델로 계속
                if i < len(FREE_MODELS) - 1:
                    await asyncio.sleep(1)  # 잠시 대기 후 다음 모델 시도
                continue

            except httpx.TimeoutException:
                logger.warning(f"{log_prefix} [{model}] 요청 타임아웃 ({API_TIMEOUT_SECONDS}초)")
                continue

            except Exception as e:
                logger.error(f"{log_prefix} [{model}] 예상치 못한 오류: {e}", exc_info=True)
                continue

    logger.error(f"{log_prefix} 모든 모델에서 요약 실패")
    return None


async def summarize_unsummarized_articles(limit: int = 50) -> dict:
    """DB에서 요약되지 않은 기사를 찾아 요약을 생성하고 저장한다.

    기사 간 딜레이를 적용하여 rate limit을 회피한다.
    limit 파라미터로 1회 실행 시 최대 처리 건수를 제한한다 (기본 50건).

    Returns:
        dict: 처리 결과 집계
    """
    start_time = time.time()

    articles = supabase_db.get_unsummarized_articles()
    if limit:
        articles = articles[:limit]

    total = len(articles)
    success_count = 0
    fail_count = 0

    logger.info(f"요약 대상 기사: {total}건")

    for idx, article in enumerate(articles, 1):
        logger.info(f"[{idx}/{total}] 요약 시작: {article.title[:60]}")

        content = article.description or article.title

        summary = await summarize_article(
            title=article.title,
            content=content,
            article_id=article.id,
        )

        ok = supabase_db.update_summary(article.id, summary)
        if ok:
            if summary:
                success_count += 1
            else:
                fail_count += 1
        else:
            logger.error(f"[Article #{article.id}] DB 업데이트 실패")
            fail_count += 1

        # 기사 간 딜레이 — rate limit 회피
        if idx < total:
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

    duration = time.time() - start_time

    result = {
        "total": total,
        "summarized": success_count,
        "failed": fail_count,
        "duration_seconds": round(duration, 2),
    }

    logger.info(
        f"요약 완료 — 성공: {success_count}, 실패: {fail_count}, "
        f"소요시간: {duration:.1f}초"
    )
    return result
