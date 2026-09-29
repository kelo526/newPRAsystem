"""凭证加密：Fernet 对称加密，密钥自动生成并写入 .env。"""
import os
from pathlib import Path

from cryptography.fernet import Fernet

from engine.parser.envcfg import _ENV_PATH, load_env

load_env()  # 确保 .env 中的密钥已加载

_KEY_NAME = "PLATFORM_FERNET_KEY"
_fernet = None


def _load_or_create_key() -> bytes:
    key = os.environ.get(_KEY_NAME, "").strip()
    if not key:
        key = Fernet.generate_key().decode()
        os.environ[_KEY_NAME] = key
        # 持久化到 .env（不存在则创建）
        line = f"{_KEY_NAME}={key}\n"
        if _ENV_PATH.exists():
            content = _ENV_PATH.read_text(encoding="utf-8")
            if _KEY_NAME not in content:
                with open(_ENV_PATH, "a", encoding="utf-8") as f:
                    f.write(line)
        else:
            Path(_ENV_PATH).write_text(line, encoding="utf-8")
    return key.encode()


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode()).decode()
