"""平台配置：统一从 server/.env 加载。"""
import os

from engine.parser.envcfg import load_env

load_env()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./newpra.db").strip()


def is_sqlite() -> bool:
    return DATABASE_URL.startswith("sqlite")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()
