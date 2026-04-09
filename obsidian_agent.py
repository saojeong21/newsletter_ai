#!/usr/bin/env python3
"""
Obsidian Agent — 로컬 스크랩 데몬
실행: python obsidian_agent.py
모바일(SSL): python obsidian_agent.py --ssl
"""

import argparse
import logging
import os
import re
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
import trafilatura
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SCRAP_QUEUE_TABLE = "scrap_queue"
ARTICLES_TABLE = "ainewsletter_items"
POLL_INTERVAL = 60  # seconds
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

FREE_MODELS = [
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemma-3-12b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]

KOREAN_SOURCES = {"AI타임스", "한국경제 IT", "ZDNet Korea", "전자신문"}

SUMMARY_PROMPT_KO = """다음 AI 뉴스 기사를 한국어로 핵심 내용만 정확히 3줄로 요약하세요.

규칙:
- 반드시 정확히 3줄로만 작성 (그 이상, 그 이하 금지)
- 각 줄은 완결된 한국어 문장 (30~80자 내외)
- 번호(1. 2. 3.), 글머리 기호(•, -, *), 제목("요약:", "핵심:") 등 일절 금지
- 요약 외 다른 텍스트 금지 (설명, 인사말, 부연 없이 3줄 문장만 출력)

제목: {title}
내용: {content}

한국어 3줄 요약:"""

SUMMARY_PROMPT_EN = """Summarize the following AI news article in exactly 3 sentences in English.

Rules:
- Write exactly 3 sentences (no more, no less)
- Each sentence must be a complete, self-contained statement (20-50 words)
- No numbering (1. 2. 3.), bullets (• - *), or headers ("Summary:", "Key points:") allowed
- Output only the 3 sentences, nothing else

Title: {title}
Content: {content}

3-sentence English summary:"""


def _is_korean_source(source_name: str) -> bool:
    return source_name in KOREAN_SOURCES


def _clean_summary(raw: str) -> Optional[str]:
    if not raw:
        return None

    text = raw.strip()
    header_pattern = re.compile(
        r'^\s*(한국어\s*\d*\s*줄\s*요약|요약|핵심\s*내용|핵심|summary|3줄\s*요약)\s*[:\s]*\s*$',
        re.IGNORECASE | re.MULTILINE,
    )
    text = header_pattern.sub('', text).strip()

    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^[\d①②③]+[.)]\s*', '', line)
        line = re.sub(r'^[•\-\*]\s+', '', line)
        line = line.strip()
        if len(line) >= 10:
            lines.append(line)

    if not lines:
        return None

    return '\n'.join(lines[:3])


def _summarize_article(title: str, content: str, source_name: str) -> Optional[str]:
    """OpenRouter 무료 모델로 기사 3줄 요약 생성 (동기, 폴백 포함)."""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY 미설정 — 요약 생략")
        return None

    prompt_template = SUMMARY_PROMPT_KO if _is_korean_source(source_name) else SUMMARY_PROMPT_EN
    prompt = prompt_template.format(title=title, content=content[:2000])

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-newsletter.local",
        "X-Title": "AI Newsletter",
    }
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.3,
    }

    for model in FREE_MODELS:
        try:
            resp = requests.post(
                OPENROUTER_BASE_URL,
                headers=headers,
                json={**payload, "model": model},
                timeout=30,
            )
            if resp.status_code in (429,) or resp.status_code >= 500:
                continue
            if resp.status_code != 200:
                continue

            data = resp.json()
            if "error" in data:
                continue

            raw = data["choices"][0]["message"]["content"].strip()
            cleaned = _clean_summary(raw)
            if cleaned:
                return cleaned
        except Exception:
            continue

    return None

app = Flask(__name__)
CORS(app, origins="*")  # 로컬 전용 데몬 — 모든 출처 허용

OBSIDIAN_DIR = Path.home() / "Documents" / "Obsidian" / "02-Areas" / "Journal"


def _write_to_obsidian(title: str, url: str, source_name: str, content: str, summary: Optional[str], scrap_dt: Optional[datetime] = None) -> str:
    """Obsidian 저널 파일에 기사를 저장하거나 이어붙인다. 저장된 파일명 반환."""
    ref = scrap_dt or datetime.now()
    # Supabase created_at은 UTC이므로 KST(+9)로 변환
    if scrap_dt is not None:
        from datetime import timezone, timedelta as _td
        ref = scrap_dt + _td(hours=9)
    today = ref.strftime("%Y-%m-%d")
    time_str = ref.strftime("%H:%M")
    file_path = OBSIDIAN_DIR / f"{today}.md"

    summary_block = ""
    if summary:
        label = "**요약:**" if source_name in KOREAN_SOURCES else "**Summary:**"
        summary_block = f"\n{label}\n{summary}\n"

    entry = (
        f"\n## [{title}]({url})\n"
        f"> 출처: {source_name} · 스크랩: {time_str}\n\n"
        f"{content.strip()}\n"
        f"{summary_block}\n"
        f"---\n"
    )

    OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if file_path.exists():
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            header = (
                f"---\ndate: {today}\ntags: [AI, newsletter]\n---\n\n"
                f"# {today} AI 뉴스 스크랩\n"
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(header + entry)
    except OSError as e:
        raise RuntimeError(f"Obsidian 파일 쓰기 실패: {e}") from e

    return f"{today}.md"


@app.route("/scrap", methods=["POST", "OPTIONS"])
def scrap():
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    url = data.get("url", "").strip()
    source_name = data.get("source_name", "").strip()

    if not url:
        return jsonify({"error": "유효하지 않은 URL입니다"}), 400

    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "URL은 http:// 또는 https://로 시작해야 합니다"}), 400

    try:
        downloaded = trafilatura.fetch_url(url)
        content = trafilatura.extract(downloaded) if downloaded else None
    except Exception as e:
        return jsonify({"error": f"본문 추출 중 오류 발생: {e}"}), 422

    if not content:
        return jsonify({"error": "본문을 가져올 수 없습니다"}), 422

    summary = _summarize_article(title, content, source_name)

    saved_file = _write_to_obsidian(title, url, source_name, content, summary)
    return jsonify({"status": "ok", "file": saved_file, "summarized": summary is not None})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supabase_base_url() -> str:
    return f"{SUPABASE_URL}/rest/v1"


def _fetch_pending_scraps() -> list:
    """Supabase에서 pending 상태의 스크랩 큐 항목을 가져온다."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return []
    try:
        resp = requests.get(
            f"{_supabase_base_url()}/{SCRAP_QUEUE_TABLE}",
            headers=_supabase_headers(),
            params={
                "status": "eq.pending",
                "order": "created_at.asc",
                "limit": "20",
                "select": "id,article_url,title,source_name,created_at",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"큐 조회 실패: {e}")
        return []


def _update_queue_status(queue_id: int, success: bool, error_message: Optional[str] = None) -> None:
    """큐 항목의 상태를 done 또는 failed로 업데이트한다."""
    payload = {
        "status": "done" if success else "failed",
        "processed_at": datetime.now().isoformat(),
    }
    if error_message:
        payload["error_message"] = error_message[:500]
    try:
        resp = requests.patch(
            f"{_supabase_base_url()}/{SCRAP_QUEUE_TABLE}",
            headers=_supabase_headers(),
            params={"id": f"eq.{queue_id}"},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"큐 상태 업데이트 실패 (id={queue_id}): {e}")


def _process_queue_item(item: dict) -> None:
    """하나의 큐 항목을 처리: 크롤링 → 요약 → Obsidian 저장."""
    queue_id = item["id"]
    url = item["article_url"]
    title = item.get("title", "")
    source_name = item.get("source_name", "")

    # created_at(UTC)을 파싱해 파일 날짜 결정에 사용
    scrap_dt: Optional[datetime] = None
    raw_created = item.get("created_at")
    if raw_created:
        try:
            scrap_dt = datetime.fromisoformat(raw_created.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass

    logger.info(f"큐 처리 시작: [{queue_id}] {title[:50]}")

    try:
        downloaded = trafilatura.fetch_url(url)
        content = trafilatura.extract(downloaded) if downloaded else None
    except Exception as e:
        _update_queue_status(queue_id, False, f"크롤링 실패: {e}")
        return

    if not content:
        _update_queue_status(queue_id, False, "본문 추출 실패")
        return

    summary = _summarize_article(title, content, source_name)
    try:
        saved_file = _write_to_obsidian(title, url, source_name, content, summary, scrap_dt)
        logger.info(f"큐 처리 완료: [{queue_id}] → {saved_file}")
        _update_queue_status(queue_id, True)
    except Exception as e:
        _update_queue_status(queue_id, False, f"Obsidian 저장 실패: {e}")


def _poll_queue() -> None:
    """백그라운드 스레드: 주기적으로 큐를 확인하고 처리한다."""
    logger.info("큐 폴링 스레드 시작")
    while True:
        try:
            items = _fetch_pending_scraps()
            if items:
                logger.info(f"처리할 큐 항목: {len(items)}건")
            for item in items:
                _process_queue_item(item)
        except Exception as e:
            logger.error(f"큐 폴링 오류: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssl", action="store_true", help="mkcert SSL 인증서로 HTTPS 실행 (모바일 지원)")
    args = parser.parse_args()

    lan_ip = _get_lan_ip()
    port = 27123

    # 큐 폴링 스레드 시작 (Supabase 설정이 있을 때만)
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        poll_thread = threading.Thread(target=_poll_queue, daemon=True)
        poll_thread.start()
        logger.info("Supabase 큐 폴링 활성화 (60초 간격)")
    else:
        logger.warning("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY 미설정 — 큐 폴링 비활성화")

    if args.ssl:
        cert = Path.home() / ".mkcert" / f"{lan_ip}+1.pem"
        key  = Path.home() / ".mkcert" / f"{lan_ip}+1-key.pem"
        if not cert.exists() or not key.exists():
            print(f"[오류] mkcert 인증서가 없습니다. 먼저 실행하세요:")
            print(f"  mkcert -install")
            print(f"  mkcert -cert-file ~/.mkcert/{lan_ip}+1.pem -key-file ~/.mkcert/{lan_ip}+1-key.pem {lan_ip} localhost")
            sys.exit(1)
        print(f"Obsidian Agent (HTTPS) running on https://0.0.0.0:{port}")
        print(f"LAN access (mobile): https://{lan_ip}:{port}")
        ssl_ctx = (str(cert), str(key))
        app.run(host="0.0.0.0", port=port, ssl_context=ssl_ctx)
    else:
        print(f"Obsidian Agent running on http://0.0.0.0:{port}")
        print(f"LAN access: http://{lan_ip}:{port}")
        print(f"(모바일 지원: python obsidian_agent.py --ssl)")
        app.run(host="0.0.0.0", port=port)
