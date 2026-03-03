# SQLAlchemy ORM 모델 정의
# Article 테이블: 수집된 뉴스 기사와 AI 요약 정보를 저장

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Article(Base):
    """뉴스 기사 모델.

    RSS 피드에서 수집된 기사 원문 정보와
    OpenRouter API로 생성된 한국어 요약을 함께 저장한다.
    """

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    source_name = Column(String, nullable=False)   # 예: "TechCrunch", "ZDNet Korea"
    source_url = Column(String)                     # RSS 피드 원본 URL
    published_at = Column(DateTime)                 # 기사 발행 일시 (피드 기준)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 수집 일시
    description = Column(Text)                      # RSS 제공 기사 본문/요약 원문
    summary_ko = Column(Text)                       # AI 생성 한국어 요약 (실패 시 NULL)
    is_summarized = Column(Boolean, default=False)  # 요약 완료 여부

    __table_args__ = (
        Index("idx_articles_collected_at", "collected_at"),
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} source='{self.source_name}' title='{self.title[:40]}...'>"
