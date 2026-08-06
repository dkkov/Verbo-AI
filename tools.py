# -*- coding: utf-8 -*-
"""
tools.py — реальное действие бота: создание заявки (tool calling).

Один инструмент create_lead. Схема отдаётся модели в app.py; когда модель решает
её вызвать, вызывается run_create_lead(). Здесь же — валидация контакта,
INSERT в Supabase и уведомление владельцу в Telegram.
"""
import re

import requests
from google.genai import types as gt

import config
from config import log
from knowledge import CONTACTS_LINE
from llm import with_retry
import db

# --------------------------------------------------------------------------- #
# Схема инструмента для модели (Gemini function declaration)                    #
# --------------------------------------------------------------------------- #
_CREATE_LEAD_DECLARATION = gt.FunctionDeclaration(
    name="create_lead",
    description=(
        "Создать заявку на бесплатное пробное занятие в школе Verbo. "
        "Вызывай ТОЛЬКО когда известны все пять полей: имя, контакт (телефон +380 "
        "или email), самооценка уровня, цель обучения и удобное время. "
        "Если каких-то полей не хватает — не вызывай инструмент, а вежливо спроси "
        "недостающее (по одному вопросу за раз)."
    ),
    parameters=gt.Schema(
        type=gt.Type.OBJECT,
        properties={
            "name": gt.Schema(type=gt.Type.STRING, description="Имя человека."),
            "contact": gt.Schema(
                type=gt.Type.STRING,
                description="Телефон в формате +380... или email.",
            ),
            "level_self_assessment": gt.Schema(
                type=gt.Type.STRING,
                description="Как человек сам оценивает свой уровень английского.",
            ),
            "goal": gt.Schema(type=gt.Type.STRING, description="Цель обучения."),
            "preferred_time": gt.Schema(
                type=gt.Type.STRING, description="Удобное время для занятий."
            ),
        },
        required=[
            "name",
            "contact",
            "level_self_assessment",
            "goal",
            "preferred_time",
        ],
    ),
)


def build_create_lead_tool() -> gt.Tool:
    """Возвращает инструмент create_lead в формате Gemini для передачи в generate()."""
    return gt.Tool(function_declarations=[_CREATE_LEAD_DECLARATION])

# --------------------------------------------------------------------------- #
# Валидация контакта                                                          #
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Телефон: +380 и ещё 9 цифр, допускаем пробелы/дефисы/скобки внутри.
_PHONE_RE = re.compile(r"^\+380[\s\-()]*\d[\s\-()\d]{7,}$")


def validate_contact(contact: str) -> bool:
    """Контакт валиден, если это email или украинский телефон +380..."""
    contact = (contact or "").strip()
    if _EMAIL_RE.match(contact):
        return True
    digits = re.sub(r"[^\d+]", "", contact)
    return bool(_PHONE_RE.match(contact)) or bool(re.match(r"^\+380\d{9}$", digits))


# --------------------------------------------------------------------------- #
# Уведомление владельцу в Telegram                                            #
# --------------------------------------------------------------------------- #
def _notify_owner(lead: dict) -> None:
    """
    Шлёт владельцу сообщение о новой заявке. Не критично: если Telegram не
    настроен или упал — только логируем, заявка уже сохранена в БД.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.info("Telegram не настроен — уведомление о заявке пропущено.")
        return

    text = (
        "🔔 Новая заявка Verbo\n"
        f"Имя: {lead.get('name')}\n"
        f"Контакт: {lead.get('contact')}\n"
        f"Уровень: {lead.get('level')}\n"
        f"Цель: {lead.get('goal')}\n"
        f"Удобное время: {lead.get('preferred_time')}\n"
        f"session_id: {lead.get('session_id')}"
    )
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    def _send():
        resp = requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
            timeout=config.CALL_TIMEOUT,
        )
        resp.raise_for_status()
        return resp

    try:
        with_retry(_send, what="telegram:notify")
    except Exception as e:  # noqa: BLE001 — не роняем успешную заявку из-за Telegram
        log.warning("Не удалось отправить уведомление в Telegram: %s", e)


# --------------------------------------------------------------------------- #
# Исполнение инструмента                                                      #
# --------------------------------------------------------------------------- #
def run_create_lead(args: dict, session_id: str) -> dict:
    """
    Выполняет create_lead. Возвращает структурированный результат для модели:
    - {"status": "invalid_contact", "message": ...} — переспросить контакт;
    - {"status": "ok", "lead": {...}}               — заявка сохранена;
    - {"status": "error", "message": ...}           — сбой, дать контакты школы.
    Сырые traceback наружу не отдаём.
    """
    contact = (args.get("contact") or "").strip()
    if not validate_contact(contact):
        return {
            "status": "invalid_contact",
            "message": (
                "Контакт не распознан. Нужен телефон в формате +380XXXXXXXXX "
                "или email. Попроси корректный контакт ещё раз."
            ),
        }

    lead_row = {
        "name": (args.get("name") or "").strip(),
        "contact": contact,
        "level": (args.get("level_self_assessment") or "").strip(),
        "goal": (args.get("goal") or "").strip(),
        "preferred_time": (args.get("preferred_time") or "").strip(),
        "source": "web-chat",
        "session_id": session_id,
        "status": "new",
    }

    try:
        saved = db.insert_lead(lead_row)
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось сохранить заявку в БД: %s", e)
        db.insert_log(session_id, "error", {"where": "insert_lead", "error": str(e)})
        return {
            "status": "error",
            "message": (
                "Заявку сейчас сохранить не удалось из-за технической ошибки. "
                f"Дай человеку прямые контакты школы: {CONTACTS_LINE}"
            ),
        }

    # Заявка сохранена — уведомляем владельца (best-effort) и логируем событие.
    _notify_owner(lead_row)
    db.insert_log(session_id, "tool", {"tool": "create_lead", "lead_id": saved.get("id")})

    return {
        "status": "ok",
        "lead": {
            "name": lead_row["name"],
            "contact": lead_row["contact"],
            "goal": lead_row["goal"],
            "preferred_time": lead_row["preferred_time"],
        },
        "message": (
            "Заявка успешно сохранена. Подтверди человеку естественным языком, "
            "что записали на бесплатное пробное, менеджер свяжется по указанному "
            "контакту, и коротко скажи, что будет дальше."
        ),
    }
