# -*- coding: utf-8 -*-
"""
prompts — загрузчик текстовых промптов.

Промпты держим отдельными .md-файлами, чтобы их можно было править без правки
кода. get("system") читает prompts/system.md. Файлы кэшируются в памяти после
первого чтения.
"""
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def get(name: str) -> str:
    """Возвращает содержимое prompts/<name>.md."""
    path = _DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
