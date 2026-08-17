# -*- coding: utf-8 -*-
"""
prompts — язык-зависимый загрузчик текстовых промптов.

Промпты держим отдельными .md-файлами по языкам: prompts/<lang>/<name>.md.
Язык берём из активного конфига школы (business.LANGUAGE). Если файла для языка
нет — фолбэк на prompts/<name>.md в корне пакета. Кэш в памяти после первого чтения.
"""
from functools import lru_cache
from pathlib import Path

import business

_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def get(name: str) -> str:
    """Возвращает содержимое prompts/<lang>/<name>.md (или корневой фолбэк)."""
    path = _DIR / business.LANGUAGE / f"{name}.md"
    if not path.exists():
        path = _DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
