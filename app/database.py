# SQLAlchemy 데이터베이스 연결 설정
# 엔진, 세션 팩토리, Base 클래스를 제공한다.
# DATABASE_URL 환경변수로 SQLite 경로를 설정한다.

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)

# 환경변수에서 DB URL 읽기 (기본값: sqlite:///app.db)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

# SQLite 파일 경로를 절대 경로로 변환
# "sqlite:///app.db" → 현재 디렉토리 기준 app.db 생성
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite:////"):
    db_filename = DATABASE_URL.replace("sqlite:///", "")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_path = os.path.join(base_dir, db_filename)
    # 쓰기 권한 없는 환경(Vercel Lambda 등)은 /tmp를 사용
    if not os.access(os.path.dirname(abs_path), os.W_OK):
        abs_path = os.path.join("/tmp", db_filename)
        logger.info("프로젝트 디렉토리 쓰기 불가 — /tmp 사용")
    DATABASE_URL = f"sqlite:///{abs_path}"

logger.info(f"데이터베이스 연결: {DATABASE_URL}")

# SQLite WAL 모드 활성화로 동시 읽기 성능 향상
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # FastAPI 비동기 환경에서 필요
    echo=False,  # SQL 쿼리 로그 출력 여부 (디버그 시 True로 변경)
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """SQLite 연결 시 WAL 모드와 외래키 제약 활성화."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 세션 팩토리 — 각 요청마다 독립적인 세션 생성
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 기반 클래스."""
    pass


def get_db():
    """FastAPI 의존성 주입용 DB 세션 제공자.

    요청 처리 완료 후 세션을 자동으로 닫는다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """DB 테이블을 자동 생성한다.

    앱 시작 시 호출되며, 이미 테이블이 존재하면 건너뛴다.
    """
    # 모델 임포트를 통해 Base에 테이블 메타데이터 등록
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("데이터베이스 테이블 초기화 완료")
