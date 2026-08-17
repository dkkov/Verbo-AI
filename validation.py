# -*- coding: utf-8 -*-
"""
validation.py — валидация контакта лида. Чистые функции без зависимостей от
config/сети, поэтому легко тестируются в изоляции.

Режимы (задаются в конфиге школы, contact_validation.mode):
- "international" — принимаем любой телефон в формате E.164 (+ и 8–15 цифр)
  или email. Подходит для международной школы.
- "ua"           — принимаем только украинский телефон +380XXXXXXXXX или email.
  Историческое поведение оригинала.
"""
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Украинский номер: +380 и ещё 9 цифр.
_UA_PHONE_RE = re.compile(r"^\+380\d{9}$")
# Международный E.164: '+' и 8–15 цифр.
_INTL_PHONE_RE = re.compile(r"^\+\d{8,15}$")


def validate_contact(contact: str, mode: str = "international") -> bool:
    """True, если контакт — валидный email или телефон по правилам режима."""
    contact = (contact or "").strip()
    if _EMAIL_RE.match(contact):
        return True
    # Оставляем только '+' и цифры (убираем пробелы, дефисы, скобки).
    digits = re.sub(r"[^\d+]", "", contact)
    if mode == "ua":
        return bool(_UA_PHONE_RE.match(digits))
    return bool(_INTL_PHONE_RE.match(digits))
