from dataclasses import dataclass
from typing import List


@dataclass
class RSSSource:
    name: str
    url: str
    category: str
    enabled: bool = True


RSS_SOURCES: List[RSSSource] = [
    RSSSource(name="TechCrunch AI", url="https://techcrunch.com/category/artificial-intelligence/feed/", category="해외 AI"),
    RSSSource(name="VentureBeat AI", url="https://venturebeat.com/category/ai/feed/", category="해외 AI"),
    RSSSource(name="The Verge AI", url="https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", category="해외 AI"),
    RSSSource(name="Google AI Blog", url="https://blog.google/technology/ai/rss/", category="해외 AI"),
    RSSSource(name="Anthropic News", url="https://www.anthropic.com/news/rss", category="해외 AI"),
    RSSSource(name="OpenAI Blog", url="https://openai.com/blog/rss/", category="해외 AI"),
    RSSSource(name="MIT Technology Review AI", url="https://www.technologyreview.com/feed/", category="해외 AI"),
    RSSSource(name="Wired AI", url="https://www.wired.com/feed/category/artificial-intelligence/latest/rss", category="해외 AI"),
    RSSSource(name="ZDNet Korea", url="https://zdnet.co.kr/rss/rss.aspx", category="국내 IT"),
    RSSSource(name="전자신문", url="https://www.etnews.com/rss/", category="국내 IT"),
    RSSSource(name="AI타임스", url="https://www.aitimes.com/rss/allArticle.xml", category="국내 AI"),
    RSSSource(name="한국경제 IT", url="https://www.hankyung.com/feed/it", category="국내 IT"),
]

AI_KEYWORDS = [
    "AI", "LLM", "GPT", "Gemini", "Claude", "ChatGPT",
    "artificial intelligence", "machine learning", "deep learning",
    "neural network", "large language model", "generative AI",
    "Nvidia", "OpenAI", "Anthropic", "DeepMind", "Perplexity",
    "Microsoft", "Google", "Meta", "Apple", "Amazon",
    "Tesla", "Palantir",
    "인공지능", "딥러닝", "머신러닝", "생성형", "거대언어모델",
    "초거대", "파운데이션모델",
    "네이버", "카카오", "삼성", "SK하이닉스", "LG전자",
    "업스테이지", "퓨리오사", "리벨리온", "포티투닷", "뤼튼",
    "KT", "현대자동차",
]

AI_NATIVE_SOURCES = {
    "TechCrunch AI", "VentureBeat AI", "The Verge AI",
    "Google AI Blog", "Anthropic News", "OpenAI Blog", "AI타임스",
}

MAX_ARTICLES_PER_FEED = 20
