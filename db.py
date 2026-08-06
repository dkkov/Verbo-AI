# -*- coding: utf-8 -*-
"""
db.py — слой доступа к Supabase.

Работаем через официальный клиент supabase-py (REST/PostgREST) с ключом
SERVICE_ROLE. Это сознательный выбор для Render с несколькими воркерами:
PostgREST держит собственный пул соединений к Postgres на стороне Supabase,
поэтому воркеры приложения НЕ открывают прямых коннектов к базе и не упираются
в лимит (проблема прямого соединения на 5432). Для случаев, когда нужен прямой
SQL, в .env.example есть DATABASE_URL через пулер на порту 6543 — см. README.

Таблицы: leads, sessions, logs, knowledge. На всех включён RLS, публичных
политик на чтение нет — доступ только с сервера по SERVICE_ROLE.
"""
from typing import Optional, Any

from supabase import create_client, Client
from supabase.client import ClientOptions

import config
from config import log
from llm import with_retry

# Клиент создаём один раз на процесс.
_client: Client = create_client(
    config.SUPABASE_URL,
    config.SUPABASE_SERVICE_ROLE_KEY,
    options=ClientOptions(
        postgrest_client_timeout=int(config.CALL_TIMEOUT),
        storage_client_timeout=int(config.CALL_TIMEOUT),
    ),
)


def client() -> Client:
    return _client


# --------------------------------------------------------------------------- #
# Сессии (память диалога): профиль + история + резюме                          #
# --------------------------------------------------------------------------- #
def get_session(session_id: str) -> Optional[dict]:
    """Возвращает строку сессии или None, если её ещё нет."""
    def _run():
        return (
            _client.table("sessions")
            .select("*")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )

    res = with_retry(_run, what="supabase:get_session")
    rows = res.data or []
    return rows[0] if rows else None


def upsert_session(session_id: str, patch: dict) -> None:
    """
    Вставляет или обновляет сессию. patch — частичный набор полей
    (name, level, goal, format, budget, summary, history, greeted).
    """
    payload = {"id": session_id, **patch}

    def _run():
        return _client.table("sessions").upsert(payload).execute()

    with_retry(_run, what="supabase:upsert_session")


# --------------------------------------------------------------------------- #
# Заявки (leads)                                                               #
# --------------------------------------------------------------------------- #
def insert_lead(lead: dict) -> dict:
    """
    Вставляет заявку в таблицу leads. Поля id/created_at/status/source
    проставляются дефолтами в БД, если не переданы. Возвращает вставленную строку.
    """
    def _run():
        return _client.table("leads").insert(lead).execute()

    res = with_retry(_run, what="supabase:insert_lead")
    rows = res.data or []
    return rows[0] if rows else {}


def list_leads(limit: int = 200) -> list[dict]:
    """Возвращает последние заявки для админ-вкладки «Заявки»."""
    def _run():
        return (
            _client.table("leads")
            .select("created_at, name, contact, level, goal, preferred_time, status, session_id")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    res = with_retry(_run, what="supabase:list_leads")
    return res.data or []


# --------------------------------------------------------------------------- #
# Логи (вердикты судьи, ошибки, события)                                       #
# --------------------------------------------------------------------------- #
def insert_log(session_id: str, kind: str, payload: dict) -> None:
    """
    Пишет событие в logs. kind: 'judge' | 'error' | 'router' | 'tool'.
    Логирование не должно ронять основной поток — ошибки глушим.
    """
    row = {"session_id": session_id, "kind": kind, "payload": payload}

    def _run():
        return _client.table("logs").insert(row).execute()

    try:
        with_retry(_run, what="supabase:insert_log")
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось записать лог (%s): %s", kind, e)


# --------------------------------------------------------------------------- #
# Синхронизация базы знаний в зеркальную таблицу knowledge                     #
# --------------------------------------------------------------------------- #
def sync_knowledge(rows: list[dict]) -> None:
    """
    Заливает строки из knowledge.knowledge_rows() в таблицу knowledge (upsert
    по паре category+key). Это зеркало для аудита; источник правды — knowledge.py.
    """
    def _run():
        return _client.table("knowledge").upsert(
            rows, on_conflict="category,key"
        ).execute()

    with_retry(_run, what="supabase:sync_knowledge")


def health_check() -> bool:
    """Лёгкий пинг БД для /health. Возвращает True, если запрос прошёл."""
    try:
        with_retry(
            lambda: _client.table("sessions").select("id").limit(1).execute(),
            what="supabase:health",
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("health_check к БД не прошёл: %s", e)
        return False
