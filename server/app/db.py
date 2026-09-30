"""数据库引擎与会话（PostgreSQL / SQLite 双兼容）。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL, is_sqlite

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite() else {},
)

if is_sqlite():
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        """调度线程 / 解析线程 / API 并发写 SQLite 时防 database is locked。"""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    from . import models  # noqa: F401 —— 确保模型注册
    Base.metadata.create_all(engine)
