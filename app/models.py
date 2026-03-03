from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    source_name = Column(String, nullable=False)
    source_url = Column(String)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(Text)
    summary_ko = Column(Text)
    is_summarized = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_articles_collected_at", "collected_at"),
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} source='{self.source_name}' title='{self.title[:40]}...'>"
