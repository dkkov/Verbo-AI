# -*- coding: utf-8 -*-
"""
memory.py — память диалога поверх Supabase.

Ключевые идеи ТЗ:
- В каждый запрос к модели уходит окно из последних HISTORY_WINDOW реплик.
- Профиль (имя, уровень, цель, формат, бюджет) извлекается по ходу разговора
  и хранится по session_id — чтобы не переспрашивать известное.
- Более старая история сворачивается в краткое резюме.
- Всё хранится в Supabase, а не в памяти процесса: инстанс на Render
  перезапускается, in-memory состояние теряется.
"""
from typing import Optional

import config
from config import MODEL_CHEAP, HISTORY_WINDOW
from llm import complete_text, complete_json
import prompts

PROFILE_FIELDS = ["name", "level", "goal", "format", "budget"]

# Человекочитаемые подписи полей профиля для системного промпта.
_PROFILE_LABELS = {
    "name": "Имя",
    "level": "Заявленный уровень",
    "goal": "Цель обучения",
    "format": "Интересующий формат",
    "budget": "Бюджет",
}


# --------------------------------------------------------------------------- #
# Загрузка контекста                                                          #
# --------------------------------------------------------------------------- #
def load_context(session_id: str) -> dict:
    """
    Возвращает всё, что нужно для сборки запроса к модели:
    {
      "history":  [{"role","content"}, ...]  — последние реплики (<= HISTORY_WINDOW),
      "profile":  {name, level, goal, format, budget},
      "summary":  str,
      "greeted":  bool,
      "name":     str,
      "exists":   bool  — была ли уже такая сессия,
    }
    """
    from db import get_session  # локальный импорт, чтобы избежать циклов при старте

    row = get_session(session_id)
    if not row:
        return {
            "history": [],
            "profile": {f: "" for f in PROFILE_FIELDS},
            "summary": "",
            "greeted": False,
            "name": "",
            "exists": False,
        }

    history = row.get("history") or []
    profile = {f: (row.get(f) or "") for f in PROFILE_FIELDS}
    return {
        "history": history[-HISTORY_WINDOW:],
        "profile": profile,
        "summary": row.get("summary") or "",
        "greeted": bool(row.get("greeted")),
        "name": profile.get("name", ""),
        "exists": True,
    }


def full_history(session_id: str) -> list[dict]:
    """Полная сохранённая история (для восстановления чата при повторном заходе)."""
    from db import get_session

    row = get_session(session_id)
    if not row:
        return []
    return row.get("history") or []


# --------------------------------------------------------------------------- #
# Запись реплик + сворачивание старой истории                                 #
# --------------------------------------------------------------------------- #
def append_message(session_id: str, role: str, content: str) -> None:
    """
    Добавляет реплику в историю сессии. Когда история перерастает 2×окна,
    самые старые реплики сворачиваются в резюме, а в истории остаётся окно.
    """
    from db import get_session, upsert_session

    row = get_session(session_id) or {}
    history = row.get("history") or []
    summary = row.get("summary") or ""

    history.append({"role": role, "content": content})

    patch = {}
    if len(history) > 2 * HISTORY_WINDOW:
        keep = history[-HISTORY_WINDOW:]
        old = history[:-HISTORY_WINDOW]
        summary = _summarize(summary, old)
        history = keep
        patch["summary"] = summary

    patch["history"] = history
    upsert_session(session_id, patch)


def _summarize(prev_summary: str, old_messages: list[dict]) -> str:
    """Сворачивает старые реплики в обновлённое резюме дешёвой моделью."""
    rendered = "\n".join(
        f"{m['role']}: {m['content']}" for m in old_messages
    )
    system = prompts.get("summary").format(
        summary=prev_summary or "(пусто)",
        old_messages=rendered,
    )
    try:
        return complete_text(
            model=MODEL_CHEAP,
            system=system,
            messages=[{"role": "user", "content": "Обнови резюме."}],
            max_tokens=400,
            temperature=0.0,
        )
    except Exception:  # noqa: BLE001 — резюме не критично, не роняем диалог
        return prev_summary


# --------------------------------------------------------------------------- #
# Профиль диалога                                                             #
# --------------------------------------------------------------------------- #
def update_profile(session_id: str, current_profile: dict, user_message: str) -> dict:
    """
    Извлекает поля профиля из нового сообщения пользователя, аккуратно
    мёржит с текущим профилем (не затирая известное) и сохраняет.
    Возвращает обновлённый профиль. При ошибке извлечения — возвращает текущий.
    """
    from db import upsert_session

    system = prompts.get("profile").format(
        profile=_profile_to_json(current_profile),
        message=user_message,
    )
    try:
        extracted = complete_json(
            model=MODEL_CHEAP,
            system=system,
            messages=[{"role": "user", "content": "Обнови профиль."}],
            max_tokens=300,
        )
    except Exception:  # noqa: BLE001 — извлечение не критично
        return current_profile

    merged = dict(current_profile)
    for field in PROFILE_FIELDS:
        new_value = (extracted.get(field) or "").strip()
        if new_value:
            merged[field] = new_value

    if merged != current_profile:
        upsert_session(session_id, {f: merged[f] for f in PROFILE_FIELDS})
    return merged


def mark_greeted(session_id: str) -> None:
    from db import upsert_session

    upsert_session(session_id, {"greeted": True})


# --------------------------------------------------------------------------- #
# Форматирование профиля для промпта                                          #
# --------------------------------------------------------------------------- #
def format_profile(profile: dict) -> str:
    """Человекочитаемый профиль для подстановки в системный промпт."""
    known = [
        f"- {_PROFILE_LABELS[f]}: {profile[f]}"
        for f in PROFILE_FIELDS
        if profile.get(f)
    ]
    if not known:
        return "(пока ничего не известно — знакомимся)"
    return "\n".join(known)


def _profile_to_json(profile: dict) -> str:
    import json

    return json.dumps(
        {f: profile.get(f, "") for f in PROFILE_FIELDS},
        ensure_ascii=False,
    )
