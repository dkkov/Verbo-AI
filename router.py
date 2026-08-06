# -*- coding: utf-8 -*-
"""
router.py — классификация входящих сообщений.

Отдельный дешёвый вызов модели со строгим JSON-ответом
{"intent": "...", "confidence": 0.0}. При confidence < 0.6 — фолбэк на GENERAL.
Роутер определяет, по какому сценарию пойдёт основной ответ (см. app.py).
"""
from config import MODEL_CHEAP
from llm import complete_json
import prompts

INTENTS = {"PRICE", "BOOKING", "GENERAL", "OFF_TOPIC"}
CONFIDENCE_FLOOR = 0.6
FALLBACK = "GENERAL"


def classify(history: list[dict], user_message: str) -> dict:
    """
    Возвращает {"intent": <INTENT>, "confidence": float, "raw": <ответ модели>}.
    history — последние реплики для контекста (список {"role","content"}).
    """
    system = prompts.get("router")

    # Даём модели немного контекста: последние реплики + текущее сообщение.
    context_messages = list(history[-6:])
    context_messages.append({"role": "user", "content": user_message})

    try:
        data = complete_json(
            model=MODEL_CHEAP,
            system=system,
            messages=context_messages,
            max_tokens=120,
        )
    except Exception:  # noqa: BLE001 — если роутер упал, безопасный фолбэк
        return {"intent": FALLBACK, "confidence": 0.0, "raw": "error"}

    intent = str(data.get("intent", "")).upper().strip()
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    # Валидация + фолбэк на GENERAL при неизвестном интенте или низкой уверенности.
    if intent not in INTENTS or confidence < CONFIDENCE_FLOOR:
        return {"intent": FALLBACK, "confidence": confidence, "raw": data}

    return {"intent": intent, "confidence": confidence, "raw": data}
