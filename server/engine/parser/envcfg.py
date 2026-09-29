"""轻量 .env 加载（server/.env），不引入额外依赖。"""
import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_loaded = False


def load_env():
    global _loaded
    if _loaded:
        return
    _loaded = True
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
