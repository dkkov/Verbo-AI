# -*- coding: utf-8 -*-
"""
tools.py — реальное действие бота: создание заявки (tool calling).

Один инструмент create_lead. Схема, описание и сообщения берутся из активного
конфига школы (business.py) и язык-зависимых строк (strings.py). Валидация
контакта вынесена в validation.py и работает по режиму из конфига
(international / ua).
"""
import requests
from google.genai import types as gt

import config
from config import log
import business
import strings
from knowledge import CONTACTS_LINE
from validation import validate_contact as _validate_contact
from llm import with_retry
import db

_GLUE = strings.glue(business.LANGUAGE)
_BUSINESS_NAME = business.BUSINESS["name"]

# --------------------------------------------------------------------------- #
# Схема инструмента для модели (Gemini function declaration)                    #
# --------------------------------------------------------------------------- #
_CREATE_LEAD_DECLARATION = gt.FunctionDeclaration(
    name="create_lead",
    description=_GLUE["tool_description"].format(business=_BUSINESS_NAME),
    parameters=gt.Schema(
        type=gt.Type.OBJECT,
        properties={
            "name": gt.Schema(type=gt.Type.STRING, description="Person's name."),
            "contact": gt.Schema(
                type=gt.Type.STRING,
                description="Phone in international format +... or an email.",
            ),
            "level_self_assessment": gt.Schema(
                type=gt.Type.STRING,
                description="How the person rates their own English level.",
            ),
            "goal": gt.Schema(type=gt.Type.STRING, description="Learning goal."),
            "preferred_time": gt.Schema(
                type=gt.Type.STRING, description="Preferred time for lessons."
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


def validate_contact(contact: str) -> bool:
    """Валидация контакта по режиму активной школы (international / ua)."""
    return _validate_contact(contact, business.CONTACT_MODE)


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
        _GLUE["notify_title"].format(business=_BUSINESS_NAME) + "\n"
        f"{_GLUE['notify_name']}: {lead.get('name')}\n"
        f"{_GLUE['notify_contact']}: {lead.get('contact')}\n"
        f"{_GLUE['notify_level']}: {lead.get('level')}\n"
        f"{_GLUE['notify_goal']}: {lead.get('goal')}\n"
        f"{_GLUE['notify_time']}: {lead.get('preferred_time')}\n"
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
        return {"status": "invalid_contact", "message": _GLUE["invalid_contact"]}

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
            "message": _GLUE["lead_error"].format(contacts=CONTACTS_LINE),
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
        "message": _GLUE["lead_ok"],
    }
