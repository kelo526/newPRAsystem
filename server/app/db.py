"""数据库引擎与会话（PostgreSQL / SQLite 双兼容）。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL, is_sqlite

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite() else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    from . import models  # noqa: F401 —— 确保模型注册
    Base.metadata.create_all(engine)
