# Obsidian 저널 스크랩 기능 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 뉴스레터 웹앱의 기사 카드에 스크랩 버튼을 추가하고, 클릭 시 원문 본문을 크롤링하여 로컬 Obsidian 저널(`~/문서/Obsidian/02-Areas/Journal/YYYY-MM-DD.md`)에 날짜별로 저장한다.

**Architecture:** 브라우저가 카드의 기사 데이터를 직접 로컬 데몬(`obsidian_agent.py`)으로 전송한다. 데몬은 trafilatura로 원문을 크롤링하고 Obsidian 파일에 append한다. Vercel 서버는 수정하지 않는다. 데스크탑은 `localhost:27123`, 모바일은 `mkcert` SSL + LAN IP를 사용한다.

**Tech Stack:** Python + Flask + trafilatura + flask-cors (데몬), Vanilla JS fetch API (프론트엔드)

---

## 파일 맵

| 파일 | 역할 | 변경 |
|---|---|---|
| `obsidian_agent.py` | 로컬 HTTP 데몬, /scrap 엔드포인트 | 신규 생성 |
| `app/templates/index.html` | 기사 카드 스크랩 버튼 + 설정 UI + JS | 수정 |
| `app/static/style.css` | 스크랩 버튼/설정 UI CSS | 수정 |
| `public/static/style.css` | 위와 동일 (Vercel CDN 동기화) | 수정 |

---

## Task 1: obsidian_agent.py — 로컬 HTTP 데몬

**Files:**
- Create: `obsidian_agent.py`

- [ ] **Step 1: 파일 생성**

`obsidian_agent.py`를 프로젝트 루트에 생성한다:

```python
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
    today = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    file_path = OBSIDIAN_DIR / f"{today}.md"

    entry = (
        f"\n## [{title}]({url})\n"
        f"> 출처: {source_name} · 스크랩: {time_str}\n\n"
        f"{content.strip()}\n\n"
        f"---\n"
    )

    OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)

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

    return f"{today}.md"


@app.route("/scrap", methods=["POST", "OPTIONS"])
def scrap():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    url = data.get("url", "").strip()
    source_name = data.get("source_name", "").strip()

    if not url:
        return jsonify({"error": "유효하지 않은 URL입니다"}), 400

    downloaded = trafilatura.fetch_url(url)
    content = trafilatura.extract(downloaded) if downloaded else None

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
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
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
```

- [ ] **Step 2: 의존성 설치 확인**

```bash
pip install flask flask-cors trafilatura
```

기대 출력: 설치 완료 또는 `already satisfied`

- [ ] **Step 3: 데몬 실행 테스트**

터미널 1:
```bash
python obsidian_agent.py
```
기대 출력:
```
Obsidian Agent running on http://0.0.0.0:27123
LAN access: http://192.168.x.x:27123
```

터미널 2 — curl로 헬스체크:
```bash
curl http://localhost:27123/health
```
기대 출력: `{"status": "ok"}`

- [ ] **Step 4: 스크랩 엔드포인트 수동 테스트**

```bash
curl -s -X POST http://localhost:27123/scrap \
  -H "Content-Type: application/json" \
  -d '{"title":"테스트 기사","url":"https://techcrunch.com/2024/03/17/anthropic-claude-3/","source_name":"TechCrunch"}'
```

기대 출력: `{"file":"2026-04-01.md","status":"ok"}`

그리고 파일 확인:
```bash
cat ~/문서/Obsidian/02-Areas/Journal/$(date +%Y-%m-%d).md
```
기대: frontmatter + 기사 섹션 존재

- [ ] **Step 5: 크롤링 실패 케이스 테스트**

```bash
curl -s -X POST http://localhost:27123/scrap \
  -H "Content-Type: application/json" \
  -d '{"title":"테스트","url":"https://example.com","source_name":"Test"}'
```
기대 출력: `{"error":"본문을 가져올 수 없습니다"}` (HTTP 422)

- [ ] **Step 6: 두 번째 기사 append 테스트**

Step 4 명령을 다시 실행하거나 다른 URL로 실행한다. `cat` 명령으로 파일을 확인했을 때 `---` 구분선 아래에 두 번째 기사가 이어붙여져 있어야 한다.

- [ ] **Step 7: 커밋**

```bash
git add obsidian_agent.py
git commit -m "feat: Obsidian 스크랩 로컬 데몬 추가 (obsidian_agent.py)"
```

---

## Task 2: index.html — 스크랩 버튼 HTML + 에이전트 설정 UI

**Files:**
- Modify: `app/templates/index.html`

- [ ] **Step 1: article 요소에 data 속성 추가**

`app/templates/index.html` 173~179줄의 `<article>` 태그에 `data-url`과 `data-source-name` 속성을 추가한다.

변경 전:
```html
    <article
        class="news-card"
        data-source="{{ src_key }}"
        data-region="{% if is_domestic %}domestic{% else %}international{% endif %}"
        data-title="{{ article.title | lower }}"
        aria-label="{{ article.source_name }} — {{ article.title }}"
    >
```

변경 후:
```html
    <article
        class="news-card"
        data-source="{{ src_key }}"
        data-region="{% if is_domestic %}domestic{% else %}international{% endif %}"
        data-title="{{ article.title | lower }}"
        data-url="{{ article.url }}"
        data-source-name="{{ article.source_name }}"
        data-original-title="{{ article.title }}"
        aria-label="{{ article.source_name }} — {{ article.title }}"
    >
```

- [ ] **Step 2: 카드 푸터에 스크랩 버튼 추가**

`app/templates/index.html` 214~227줄의 `card-footer`를 수정한다.

변경 전:
```html
            <!-- 카드 푸터: 태그 + 원문 링크 -->
            <div class="card-footer">
                <div class="card-tags">
                    <span class="tag-region {% if is_domestic %}domestic{% else %}international{% endif %}">
                        {% if is_domestic %}국내{% else %}해외{% endif %}
                    </span>
                    {% if article.is_summarized and article.summary_ko %}
                        <span class="ai-badge">AI 요약</span>
                    {% endif %}
                </div>
                <a href="{{ article.url }}" target="_blank" rel="noopener noreferrer" class="read-more-link">
                    원문 보기 →
                </a>
            </div>
```

변경 후:
```html
            <!-- 카드 푸터: 태그 + 액션 -->
            <div class="card-footer">
                <div class="card-tags">
                    <span class="tag-region {% if is_domestic %}domestic{% else %}international{% endif %}">
                        {% if is_domestic %}국내{% else %}해외{% endif %}
                    </span>
                    {% if article.is_summarized and article.summary_ko %}
                        <span class="ai-badge">AI 요약</span>
                    {% endif %}
                </div>
                <div class="card-actions">
                    <button
                        class="scrap-btn"
                        aria-label="Obsidian에 스크랩"
                        title="Obsidian에 스크랩"
                    >
                        <span class="scrap-icon" aria-hidden="true">🔖</span>
                        <span class="scrap-label">스크랩</span>
                    </button>
                    <a href="{{ article.url }}" target="_blank" rel="noopener noreferrer" class="read-more-link">
                        원문 보기 →
                    </a>
                </div>
            </div>
```

- [ ] **Step 3: 에이전트 URL 설정 UI 추가 (히어로 컨트롤 아래)**

`app/templates/index.html` 85~86줄 사이 (`</section>` 닫는 태그 바로 앞)에 설정 행을 추가한다.

변경 전:
```html
    </div>
</section>

<!-- ── 빠른 날짜 탐색 칩 ── -->
```

변경 후:
```html
    </div>

    <!-- 에이전트 URL 설정 (Obsidian 스크랩용) -->
    <div class="agent-settings" id="agentSettings">
        <button class="agent-settings-toggle" id="agentSettingsToggle" aria-expanded="false" aria-controls="agentSettingsPanel">
            <span aria-hidden="true">⚙</span> Obsidian 에이전트 설정
        </button>
        <div class="agent-settings-panel" id="agentSettingsPanel" hidden>
            <label for="agentUrlInput" class="agent-url-label">
                에이전트 URL
                <span class="agent-url-hint">(모바일: https://192.168.x.x:27123)</span>
            </label>
            <div class="agent-url-row">
                <input
                    type="url"
                    id="agentUrlInput"
                    class="agent-url-input"
                    placeholder="http://localhost:27123"
                    autocomplete="off"
                >
                <button class="btn btn-sm btn-primary" id="agentUrlSaveBtn">저장</button>
            </div>
        </div>
    </div>
</section>

<!-- ── 빠른 날짜 탐색 칩 ── -->
```

- [ ] **Step 4: 브라우저에서 HTML 구조 확인**

로컬 서버 실행:
```bash
uvicorn app.main:app --reload
```

`http://localhost:8000` 방문. 기사 카드 하단에 🔖 스크랩 버튼이 보여야 하고, 히어로 섹션 아래에 ⚙ Obsidian 에이전트 설정 토글이 보여야 한다.

- [ ] **Step 5: 커밋**

```bash
git add app/templates/index.html
git commit -m "feat: 스크랩 버튼 + 에이전트 설정 UI HTML 추가"
```

---

## Task 3: index.html — 스크랩 JavaScript 로직

**Files:**
- Modify: `app/templates/index.html` ({% block scripts %} 섹션)

- [ ] **Step 1: 스크랩 JS 블록 추가**

`app/templates/index.html`의 `{% block scripts %}` 안 (`</script>` 닫는 태그 직전)에 다음 코드를 추가한다. 기존 스크립트 블록 맨 끝 `</script>` 바로 앞에 삽입한다.

변경 전 (443~444줄):
```javascript
    })();
</script>
{% endblock %}
```

변경 후:
```javascript
    })();

    /* ──────────────────────────────────────────
       Obsidian 에이전트 설정 패널
    ────────────────────────────────────────── */
    (function() {
        var STORAGE_KEY = 'obsidian_agent_url';
        var DEFAULT_URL = 'http://localhost:27123';

        var toggle = document.getElementById('agentSettingsToggle');
        var panel  = document.getElementById('agentSettingsPanel');
        var input  = document.getElementById('agentUrlInput');
        var saveBtn = document.getElementById('agentUrlSaveBtn');

        if (!toggle || !panel || !input) return;

        // 저장된 URL 복원
        input.value = localStorage.getItem(STORAGE_KEY) || DEFAULT_URL;

        toggle.addEventListener('click', function() {
            var isOpen = !panel.hidden;
            panel.hidden = isOpen;
            toggle.setAttribute('aria-expanded', String(!isOpen));
        });

        saveBtn.addEventListener('click', function() {
            var val = input.value.trim() || DEFAULT_URL;
            localStorage.setItem(STORAGE_KEY, val);
            showToast({ type: 'success', title: '저장됨', message: '에이전트 URL이 저장되었습니다.' });
            panel.hidden = true;
            toggle.setAttribute('aria-expanded', 'false');
        });

        window.__getAgentUrl = function() {
            return localStorage.getItem(STORAGE_KEY) || DEFAULT_URL;
        };
    })();

    /* ──────────────────────────────────────────
       스크랩 버튼 핸들러
    ────────────────────────────────────────── */
    (function() {
        var scrapBtns = document.querySelectorAll('.scrap-btn');
        if (!scrapBtns.length) return;

        function handleScrap(btn) {
            var card = btn.closest('.news-card');
            if (!card) return;

            var title      = card.getAttribute('data-original-title') || '';
            var url        = card.getAttribute('data-url') || '';
            var sourceName = card.getAttribute('data-source-name') || '';

            if (!url) {
                showToast({ type: 'error', title: '오류', message: 'URL을 찾을 수 없습니다.' });
                return;
            }

            // 로딩 상태
            btn.disabled = true;
            btn.classList.add('scrap-loading');
            var iconEl  = btn.querySelector('.scrap-icon');
            var labelEl = btn.querySelector('.scrap-label');
            if (iconEl)  iconEl.textContent  = '⏳';
            if (labelEl) labelEl.textContent = '저장 중...';

            var agentUrl = (typeof window.__getAgentUrl === 'function')
                ? window.__getAgentUrl()
                : 'http://localhost:27123';

            fetch(agentUrl + '/scrap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title, url: url, source_name: sourceName })
            })
            .then(function(res) {
                return res.json().then(function(data) {
                    return { ok: res.ok, status: res.status, data: data };
                });
            })
            .then(function(result) {
                if (result.ok) {
                    // 성공 — 버튼을 완료 상태로 고정
                    btn.classList.remove('scrap-loading');
                    btn.classList.add('scrap-done');
                    if (iconEl)  iconEl.textContent  = '✅';
                    if (labelEl) labelEl.textContent = '저장됨';
                    showToast({ type: 'success', title: 'Obsidian에 저장됨', message: result.data.file || '' });
                } else {
                    // 서버 오류 (크롤링 실패 등)
                    var errMsg = (result.data && result.data.error) || '저장에 실패했습니다.';
                    showToast({ type: 'error', title: '스크랩 실패', message: errMsg });
                    _resetScrapBtn(btn, iconEl, labelEl);
                }
            })
            .catch(function() {
                showToast({
                    type: 'error',
                    title: '에이전트 연결 실패',
                    message: 'obsidian_agent.py를 먼저 실행하세요.'
                });
                _resetScrapBtn(btn, iconEl, labelEl);
            });
        }

        function _resetScrapBtn(btn, iconEl, labelEl) {
            btn.disabled = false;
            btn.classList.remove('scrap-loading');
            if (iconEl)  iconEl.textContent  = '🔖';
            if (labelEl) labelEl.textContent = '스크랩';
        }

        scrapBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (btn.classList.contains('scrap-done')) return; // 이미 저장됨
                handleScrap(btn);
            });
        });
    })();
</script>
{% endblock %}
```

- [ ] **Step 2: 브라우저 콘솔에서 수동 테스트**

obsidian_agent.py를 실행한 상태에서 `http://localhost:8000` 방문.

1. 기사 카드의 🔖 스크랩 버튼 클릭
2. 버튼이 ⏳ "저장 중..."으로 변경되어야 함
3. 성공 시 ✅ "저장됨"으로 변경 + 성공 토스트 표시
4. Obsidian 파일 확인: `cat ~/문서/Obsidian/02-Areas/Journal/$(date +%Y-%m-%d).md`

- [ ] **Step 3: 데몬 미실행 에러 테스트**

obsidian_agent.py를 **종료**한 상태에서 스크랩 버튼 클릭.

기대: "에이전트 연결 실패 — obsidian_agent.py를 먼저 실행하세요." 에러 토스트 표시, 버튼이 초기 상태로 복귀.

- [ ] **Step 4: 에이전트 설정 저장 테스트**

⚙ 설정 토글 클릭 → URL 입력 → 저장 버튼 클릭 → 성공 토스트 확인.
브라우저 개발자도구 → Application → Local Storage에서 `obsidian_agent_url` 키 확인.

- [ ] **Step 5: 커밋**

```bash
git add app/templates/index.html
git commit -m "feat: 스크랩 버튼 JS 로직 추가 (에이전트 연동, 토스트, 상태 관리)"
```

---

## Task 4: CSS — 스크랩 버튼 + 설정 UI 스타일

**Files:**
- Modify: `app/static/style.css`
- Modify: `public/static/style.css`

두 파일에 **동일한 CSS**를 추가한다. `app/static/style.css` 파일의 맨 끝에 추가 후, `public/static/style.css`에도 동일하게 적용한다.

- [ ] **Step 1: app/static/style.css에 CSS 추가**

`app/static/style.css` 파일 맨 끝에 다음을 추가한다:

```css
/* ── Obsidian 스크랩 버튼 ── */
.card-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.scrap-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.25rem 0.6rem;
    font-size: var(--font-size-xs);
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    cursor: pointer;
    transition: var(--transition);
    white-space: nowrap;
}

.scrap-btn:hover:not(:disabled):not(.scrap-done) {
    color: var(--accent);
    border-color: var(--accent-mid);
    background: var(--accent-light);
}

.scrap-btn:disabled {
    cursor: not-allowed;
    opacity: 0.7;
}

.scrap-btn.scrap-done {
    color: var(--success);
    border-color: #a7f3d0;
    background: #ecfdf5;
    cursor: default;
}

.scrap-btn.scrap-loading {
    color: var(--text-muted);
}

.scrap-icon {
    font-size: 0.85em;
    line-height: 1;
}

.scrap-label {
    font-size: var(--font-size-xs);
}

/* ── 에이전트 설정 UI ── */
.agent-settings {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    margin-top: 0.5rem;
}

.agent-settings-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.2rem 0.4rem;
    border-radius: var(--radius-sm);
    transition: var(--transition);
}

.agent-settings-toggle:hover {
    color: var(--text-secondary);
    background: var(--surface-alt);
}

.agent-settings-panel {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 0.75rem 1rem;
    width: 100%;
    max-width: 420px;
}

.agent-url-label {
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--text-secondary);
}

.agent-url-hint {
    font-weight: 400;
    color: var(--text-muted);
    margin-left: 0.3rem;
}

.agent-url-row {
    display: flex;
    gap: 0.5rem;
}

.agent-url-input {
    flex: 1;
    padding: 0.4rem 0.75rem;
    font-size: var(--font-size-sm);
    font-family: var(--font-body);
    color: var(--text-primary);
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    outline: none;
    transition: border-color 0.15s;
}

.agent-url-input:focus {
    border-color: var(--accent);
}

/* hidden attribute 지원 */
[hidden] {
    display: none !important;
}

/* 모바일 스크랩 버튼 터치 영역 확보 */
@media (max-width: 640px) {
    .scrap-btn {
        padding: 0.35rem 0.75rem;
    }
    .agent-settings {
        align-items: stretch;
    }
    .agent-settings-panel {
        max-width: 100%;
    }
}
```

- [ ] **Step 2: public/static/style.css에 동일한 CSS 추가**

Step 1과 **동일한 CSS 블록**을 `public/static/style.css` 파일 맨 끝에 추가한다.

- [ ] **Step 3: 시각적 확인**

`http://localhost:8000` 새로고침.

확인 항목:
- 기사 카드 하단에 🔖 스크랩 버튼이 "원문 보기" 왼쪽에 붙어있어야 함
- 버튼 hover 시 보라색으로 변해야 함
- ⚙ 설정 토글 클릭 시 패널이 열려야 함
- 모바일 브라우저 시뮬레이터(개발자도구)에서 터치 영역이 충분해야 함

- [ ] **Step 4: 커밋**

```bash
git add app/static/style.css public/static/style.css
git commit -m "feat: 스크랩 버튼 + 에이전트 설정 UI CSS 추가"
```

---

## Task 5: 전체 통합 테스트 + Git Push

- [ ] **Step 1: 전체 흐름 테스트**

터미널 1:
```bash
python obsidian_agent.py
```

터미널 2:
```bash
uvicorn app.main:app --reload
```

브라우저에서 `http://localhost:8000` 접속:

1. 기사 카드 스크랩 버튼 클릭 → ⏳ → ✅ "Obsidian에 저장됨" 토스트 확인
2. 동일 날짜 다른 기사 스크랩 → 파일에 `---` 구분선으로 이어붙여졌는지 확인
3. 이미 스크랩된 카드 재클릭 시 아무 동작 없어야 함
4. obsidian_agent.py 종료 후 스크랩 시도 → "에이전트 연결 실패" 토스트 확인
5. ⚙ 설정 → URL 변경 → 저장 → localStorage에 저장 확인

- [ ] **Step 2: Obsidian에서 파일 확인**

Obsidian 앱에서 `02-Areas/Journal/2026-04-01.md` 열기.

확인 항목:
- frontmatter (date, tags) 정상
- `# YYYY-MM-DD AI 뉴스 스크랩` 헤더
- 기사별 `## [제목](url)` + 출처 인용구 + 본문
- 기사 간 `---` 구분선

- [ ] **Step 3: 모바일 테스트 (선택, SSL 필요)**

데스크탑 LAN IP 확인:
```bash
python obsidian_agent.py  # LAN access 줄에서 IP 확인
```

모바일 브라우저에서 `https://newsletter-ai-saojeong21s-projects.vercel.app` 접속.
⚙ 설정에서 에이전트 URL을 `http://192.168.x.x:27123`으로 변경 (또는 SSL 설정 후 `https://...`).

> **Note:** HTTPS 페이지에서 HTTP 로컬 IP 호출은 혼합 콘텐츠(mixed content) 정책으로 차단될 수 있음. SSL 필요 시:
> ```bash
> brew install mkcert
> mkcert -install
> LAN_IP=$(python3 -c "import socket; s=socket.socket(); s.connect(('8.8.8.8',80)); print(s.getsockname()[0])")
> mkdir -p ~/.mkcert
> mkcert -cert-file ~/.mkcert/${LAN_IP}+1.pem -key-file ~/.mkcert/${LAN_IP}+1-key.pem $LAN_IP localhost
> python obsidian_agent.py --ssl
> ```
> 그리고 모바일 기기에서 mkcert 루트 CA를 신뢰하도록 설정 (각 OS별 방법 상이).

- [ ] **Step 4: 최종 커밋 + push**

```bash
git add -A
git status  # 변경 파일 확인
git push origin main
```

- [ ] **Step 5: CLAUDE.md 업데이트**

CLAUDE.md 개발 이력 섹션에 16차 작업 내용 추가:

```markdown
- **16차 (2026-04-01)**: Obsidian 저널 스크랩 기능
  - 기사 카드에 🔖 스크랩 버튼 추가
  - `obsidian_agent.py` 로컬 데몬: trafilatura 크롤링 → `~/문서/Obsidian/02-Areas/Journal/YYYY-MM-DD.md` append
  - 에이전트 URL 설정 UI (localStorage) — 모바일 LAN IP 지원
  - SSL 옵션 (`--ssl` 플래그, mkcert) — 모바일 혼합 콘텐츠 우회
```

CLAUDE.md 수정 후 `wc -l CLAUDE.md`로 200줄 이하인지 확인. 초과 시 개발 이력을 압축한다.

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md에 16차 작업 이력 반영"
git push origin main
```
