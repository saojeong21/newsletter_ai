#!/usr/bin/env python3
"""
Obsidian Agent — 로컬 스크랩 데몬
실행: python obsidian_agent.py
모바일(SSL): python obsidian_agent.py --ssl
"""

import argparse
import socket
import os
import sys
from datetime import datetime
from pathlib import Path

import trafilatura
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")  # 로컬 전용 데몬 — 모든 출처 허용

OBSIDIAN_DIR = Path.home() / "문서" / "Obsidian" / "02-Areas" / "Journal"


def _write_to_obsidian(title: str, url: str, source_name: str, content: str) -> str:
    """Obsidian 저널 파일에 기사를 저장하거나 이어붙인다. 저장된 파일명 반환."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    file_path = OBSIDIAN_DIR / f"{today}.md"

    entry = (
        f"\n## [{title}]({url})\n"
        f"> 출처: {source_name} · 스크랩: {time_str}\n\n"
        f"{content.strip()}\n\n"
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

    saved_file = _write_to_obsidian(title, url, source_name, content)
    return jsonify({"status": "ok", "file": saved_file})


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssl", action="store_true", help="mkcert SSL 인증서로 HTTPS 실행 (모바일 지원)")
    args = parser.parse_args()

    lan_ip = _get_lan_ip()
    port = 27123

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
