"""
数据库连接层：SQLite + SQLAlchemy。
本地单用户 demo 定位，单文件库即可；后续迁移 PostgreSQL 只需改 DB_URL。
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = f"sqlite:///{(DATA_DIR / 'doc_system.db').as_posix()}"

# check_same_thread=False：FastAPI 线程池内使用 SQLite 的常规配置
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """启动期建表（已存在则跳过）。模型需在调用前完成导入。"""
    from db import models  # noqa: F401  确保模型注册到 Base.metadata

    Base.metadata.create_all(engine)
    _migrate_tasks_title()


def _migrate_tasks_title() -> None:
    """轻量迁移：旧库 tasks 表无 title 列时补列。
    create_all 不会给已存在的表加列，需显式 ALTER。"""
    from sqlalchemy import text  # noqa: F401

    with engine.connect() as conn:
        cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(tasks)").fetchall()]
        if cols and "title" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE tasks ADD COLUMN title VARCHAR(255) NOT NULL DEFAULT ''"
            )
            conn.commit()
