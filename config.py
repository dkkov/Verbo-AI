# -*- coding: utf-8 -*-
"""
config.py — единая точка конфигурации: переменные окружения, клиенты, константы.

Все секреты приходят из окружения (на Render — через Environment, локально —
через .env, который читает python-dotenv). В репозитории секретов нет, только
.env.example.
"""
import os
import logging

from dotenv import load_dotenv

load_dotenv()  # локально подтягивает .env; на Render переменные уже в окружении

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("verbo")


def _require(name: str, *aliases: str) -> str:
    """Обязательная переменная окружения (с алиасами) — падаем на старте, если её нет."""
    for candidate in (name, *aliases):
        value = os.environ.get(candidate)
        if value:
            return value
    raise RuntimeError(f"Не задана обязательная переменная окружения: {name}")


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# --- Модель (Google Gemini по API) ------------------------------------------
# Принимаем GEMINI_API_KEY или GOOGLE_API_KEY (алиас, который понимает и сам SDK).
GEMINI_API_KEY = _require("GEMINI_API_KEY", "GOOGLE_API_KEY")
# Основная модель для ответов пользователю. Пиним конкретную версию: псевдоним
# gemini-flash-latest периодически отдаёт 503 «high demand» (перегрузка бэкенда),
# и тогда каждый ответ падает в аварийную заглушку. gemini-3.6-flash стабильнее и
# держит отдельную квоту бесплатного тарифа. Переопределяется через env при желании.
MODEL_MAIN = _optional("GEMINI_MODEL_MAIN", "gemini-3.6-flash")
# Дешёвая быстрая модель для роутера, судьи и извлечения профиля.
MODEL_CHEAP = _optional("GEMINI_MODEL_CHEAP", "gemini-flash-lite-latest")

# --- Supabase ---------------------------------------------------------------
# SERVICE_ROLE_KEY используется ТОЛЬКО на сервере (обходит RLS для наших вставок
# и чтения заявок в админке). В клиентский код не попадает никогда.
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _require("SUPABASE_SERVICE_ROLE_KEY")

# --- Telegram-уведомления владельцу -----------------------------------------
TELEGRAM_BOT_TOKEN = _optional("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _optional("TELEGRAM_CHAT_ID")

# --- Админка «Заявки» -------------------------------------------------------
ADMIN_PASSWORD = _optional("ADMIN_PASSWORD", "")

# --- Сетевые настройки ------------------------------------------------------
# Таймаут на любой внешний вызов (модель, Supabase, Telegram), секунды.
CALL_TIMEOUT = float(_optional("CALL_TIMEOUT", "45"))
# Сколько последних реплик держим в активном контексте.
HISTORY_WINDOW = int(_optional("HISTORY_WINDOW", "12"))
# Порт для Render (Render задаёт PORT сам). Локально — 7860.
PORT = int(_optional("PORT", "7860"))

# --- Gemini-клиент ----------------------------------------------------------
from google import genai  # noqa: E402  (после чтения ключей — так нагляднее)
from google.genai import types as genai_types  # noqa: E402

# timeout в HttpOptions задаётся в МИЛЛИсекундах. Ретраи мы делаем сами через
# llm.with_retry (ровно один ретрай), чтобы поведение было одинаковым для
# модели, Supabase и Telegram.
gemini_client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=genai_types.HttpOptions(timeout=int(CALL_TIMEOUT * 1000)),
)
