# RSS 뉴스 소스 목록 설정
# 여기에서 소스를 추가/삭제하면 수집 대상이 자동으로 반영된다.
# 코드 변경 없이 소스 관리가 가능하도록 설정 파일로 분리했다.

from dataclasses import dataclass, field
from typing import List


@dataclass
class RSSSource:
    """RSS 피드 소스 정의."""
    name: str           # 표시 이름 (예: "TechCrunch AI")
    url: str            # RSS 피드 URL
    category: str       # 카테고리 ("해외 AI" 또는 "국내 IT")
    enabled: bool = True


# 수집 대상 RSS 소스 목록
RSS_SOURCES: List[RSSSource] = [
    # ===== 해외 AI 뉴스 =====
    RSSSource(
        name="TechCrunch AI",
        url="https://techcrunch.com/category/artificial-intelligence/feed/",
        category="해외 AI",
    ),
    RSSSource(
        name="VentureBeat AI",
        url="https://feeds.feedburner.com/venturebeat/SZYF",  # feedburner URL로 교체 (2026-03)
        category="해외 AI",
    ),
    RSSSource(
        name="The Verge AI",
        url="https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        category="해외 AI",
    ),
    RSSSource(
        name="Google AI Blog",
        url="https://blog.google/technology/ai/rss/",
        category="해외 AI",
    ),
    RSSSource(
        name="Anthropic News",
        url="https://www.anthropic.com/news/rss",
        category="해외 AI",
        enabled=False,  # 404 — RSS 피드 미제공
    ),
    RSSSource(
        name="OpenAI Blog",
        url="https://openai.com/blog/rss/",
        category="해외 AI",
        enabled=False,  # 403 Forbidden — RSS 피드 차단됨
    ),
    RSSSource(
        name="MIT Technology Review AI",
        url="https://www.technologyreview.com/feed/",
        category="해외 AI",
    ),
    RSSSource(
        name="Wired AI",
        url="https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
        category="해외 AI",
        enabled=False,  # 404 — RSS 피드 URL 변경됨
    ),
    RSSSource(
        name="Hugging Face Blog",
        url="https://huggingface.co/blog/feed.xml",
        category="해외 AI",
    ),
    RSSSource(
        name="AI News",
        url="https://www.artificialintelligence-news.com/feed/",
        category="해외 AI",
    ),
    RSSSource(
        name="Ars Technica AI",
        url="https://feeds.arstechnica.com/arstechnica/technology-lab",
        category="해외 AI",
    ),
    # ===== 국내 IT/AI 뉴스 =====
    RSSSource(
        name="ZDNet Korea",
        url="https://zdnet.co.kr/rss/rss.aspx",
        category="국내 IT",
        enabled=False,  # 404 — 피드 URL 변경됨
    ),
    RSSSource(
        name="전자신문",
        url="https://www.etnews.com/rss/",
        category="국내 IT",
        enabled=False,  # XML 파싱 오류 (undefined entity)
    ),
    RSSSource(
        name="AI타임스",
        url="https://www.aitimes.com/rss/allArticle.xml",
        category="국내 AI",
    ),
    RSSSource(
        name="한국경제 IT",
        url="https://www.hankyung.com/feed/it",
        category="국내 IT",
    ),
]

# AI 관련 기사 필터링 키워드
# 국내 소스는 모든 기사를 수집하면 AI와 무관한 기사가 포함될 수 있으므로
# 이 키워드 목록으로 AI 관련 기사만 선별한다.
AI_KEYWORDS = [
    # 영문 AI 관련
    "AI", "LLM", "GPT", "Gemini", "Claude", "ChatGPT",
    "artificial intelligence", "machine learning", "deep learning",
    "neural network", "large language model", "generative AI",
    "Nvidia", "OpenAI", "Anthropic", "DeepMind", "Perplexity",
    "Microsoft", "Google", "Meta", "Apple", "Amazon",
    "Tesla", "Palantir",
    # 한국어 AI 관련
    "인공지능", "딥러닝", "머신러닝", "생성형", "거대언어모델",
    "초거대", "파운데이션모델",
    # 한국 AI/IT 기업
    "네이버", "카카오", "삼성", "SK하이닉스", "LG전자",
    "업스테이지", "퓨리오사", "리벨리온", "포티투닷", "뤼튼",
    "KT", "현대자동차",
]

# AI 관련 소스는 전체 기사 수집 (키워드 필터링 불필요)
AI_NATIVE_SOURCES = {
    "TechCrunch AI",
    "VentureBeat AI",
    "The Verge AI",
    "Google AI Blog",
    "Anthropic News",
    "OpenAI Blog",
    "Hugging Face Blog",
    "AI News",
    "AI타임스",
}

# 피드당 최대 수집 기사 수
MAX_ARTICLES_PER_FEED = 20
