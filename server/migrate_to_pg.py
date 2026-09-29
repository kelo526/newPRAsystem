"""一次性迁移：SQLite (newpra.db) → PostgreSQL (localhost:5433/newpra)。"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ParseRequest, PageProfile, Task, TaskRun, TargetSystem

SQLITE_URL = "sqlite:///./newpra.db"
PG_URL = "postgresql+psycopg2://postgres:newpra2026@localhost:5433/newpra"

sqlite_e = create_engine(SQLITE_URL)
pg_e = create_engine(PG_URL)

# 1. PG 建表（与平台模型一致）
Base.metadata.create_all(pg_e)

TABLES = [TargetSystem, ParseRequest, PageProfile, Task, TaskRun]

with Session(sqlite_e) as src, Session(pg_e) as dst:
    total = 0
    for model in TABLES:
        rows = src.query(model).all()
        for r in rows:
            dst.merge(r)
        print(f"  {model.__tablename__}: {len(rows)} 行")
        total += len(rows)
    dst.commit()

    # 同步 PG 自增序列到当前最大 id
    for model in TABLES:
        t = model.__tablename__
        dst.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {t}), 1))"
        ))
    dst.commit()
    print(f"迁移完成，共 {total} 行，序列已同步")
