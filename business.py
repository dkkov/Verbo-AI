# -*- coding: utf-8 -*-
"""
business.py — загрузка конфига активной школы (тенанта).

Какой конфиг брать — задаёт переменная окружения SCHOOL_CONFIG
(по умолчанию configs/verbo_ru.yaml, чтобы поведение совпадало с оригиналом).
Смена ниши/языка = новый YAML + смена SCHOOL_CONFIG, без правки кода.

Модуль не зависит от секретов/сети — его можно импортировать и тестировать
в изоляции.
"""
import os
from pathlib import Path

import yaml

_DEFAULT = "configs/verbo_ru.yaml"


def _load() -> dict:
    raw = os.environ.get("SCHOOL_CONFIG", _DEFAULT)
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    if not path.exists():
        raise RuntimeError(f"Конфиг школы не найден: {path} (SCHOOL_CONFIG={raw})")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"Конфиг школы пуст или некорректен: {path}")
    return data


_CFG = _load()

LANGUAGE: str = _CFG.get("language", "ru")
CURRENCY: str = _CFG.get("currency", "")

BUSINESS: dict = _CFG["business"]
FORMATS: list = _CFG["formats"]
PACKAGES: list = _CFG["packages"]
DIRECTIONS: list = _CFG["directions"]
TEACHERS: list = _CFG["teachers"]
TEACHERS_SUMMARY: str = _CFG.get("teachers_summary", "")
POLICIES: dict = _CFG["policies"]
CONTACTS: dict = _CFG["contacts"]
CONTACT_MODE: str = (_CFG.get("contact_validation") or {}).get("mode", "international")
UI: dict = _CFG.get("ui", {})
