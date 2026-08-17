# -*- coding: utf-8 -*-
"""
strings.py — служебные строки по языкам (метки базы знаний и модель-facing склейка).

Здесь НЕ бизнес-контент (он в configs/<tenant>.yaml), а язык-зависимые ярлыки и
техническая склейка: заголовки разделов базы знаний, шаблон строки контактов,
сообщения инструмента create_lead, обратная связь судьи, описание инструмента.

Выбор языка — по business.LANGUAGE. Для нового языка добавь сюда блок.
"""

# Метки разделов базы знаний (подставляются в render_knowledge).
LABELS = {
    "ru": {
        "school": "ШКОЛА",
        "formats_header": "ФОРМАТЫ ЗАНЯТИЙ:",
        "packages_header": "ПАКЕТЫ:",
        "levels": "УРОВНИ",
        "schedule": "РАСПИСАНИЕ",
        "platform": "ПЛАТФОРМА",
        "directions": "НАПРАВЛЕНИЯ",
        "teachers_header": "ПРЕПОДАВАТЕЛИ:",
        "policies_header": "УСЛОВИЯ:",
        "contacts_header": "КОНТАКТЫ:",
        "phone": "Телефон",
        "email": "Email",
        "telegram": "Telegram",
    },
    "en": {
        "school": "SCHOOL",
        "formats_header": "LESSON FORMATS:",
        "packages_header": "PACKAGES:",
        "levels": "LEVELS",
        "schedule": "SCHEDULE",
        "platform": "PLATFORM",
        "directions": "DIRECTIONS",
        "teachers_header": "TEACHERS:",
        "policies_header": "TERMS:",
        "contacts_header": "CONTACTS:",
        "phone": "Phone",
        "email": "Email",
        "telegram": "Telegram",
    },
}

# Шаблон короткой строки контактов (для фолбэков). Поля: phone, email, telegram.
CONTACTS_LINE_TMPL = {
    "ru": "Телефон {phone}, email {email}, Telegram {telegram}.",
    "en": "Phone {phone}, email {email}, Telegram {telegram}.",
}

# Служебные сообщения инструмента create_lead и судьи (модель-facing).
# {business}, {contacts}, {issues} подставляются в месте использования.
GLUE = {
    "ru": {
        "judge_user": "Проверь черновик.",
        "judge_feedback": (
            "Твой предыдущий вариант ответа не прошёл внутреннюю проверку качества. "
            "Исправь следующие замечания и дай новый ответ, оставаясь в рамках базы "
            "знаний и правил тона:\n{issues}"
        ),
        "invalid_contact": (
            "Контакт не распознан. Нужен корректный телефон в международном формате "
            "(+...) или email. Попроси корректный контакт ещё раз."
        ),
        "lead_error": (
            "Заявку сейчас сохранить не удалось из-за технической ошибки. "
            "Дай человеку прямые контакты школы: {contacts}"
        ),
        "lead_ok": (
            "Заявка успешно сохранена. Подтверди человеку естественным языком, "
            "что записали на бесплатное пробное, менеджер свяжется по указанному "
            "контакту, и коротко скажи, что будет дальше."
        ),
        "notify_title": "🔔 Новая заявка {business}",
        "notify_name": "Имя",
        "notify_contact": "Контакт",
        "notify_level": "Уровень",
        "notify_goal": "Цель",
        "notify_time": "Удобное время",
        "tool_description": (
            "Создать заявку на бесплатное пробное занятие в школе «{business}». "
            "Вызывай ТОЛЬКО когда известны все пять полей: имя, контакт (телефон "
            "в международном формате +... или email), самооценка уровня, цель "
            "обучения и удобное время. Если каких-то полей не хватает — не вызывай "
            "инструмент, а вежливо спроси недостающее (по одному вопросу за раз)."
        ),
    },
    "en": {
        "judge_user": "Review the draft.",
        "judge_feedback": (
            "Your previous answer did not pass the internal quality check. "
            "Fix the following issues and give a new answer, staying within the "
            "knowledge base and the tone rules:\n{issues}"
        ),
        "invalid_contact": (
            "Contact not recognised. A valid phone in international format (+...) "
            "or an email is required. Ask for a correct contact again."
        ),
        "lead_error": (
            "The request could not be saved right now due to a technical error. "
            "Give the person the school's direct contacts: {contacts}"
        ),
        "lead_ok": (
            "The request was saved successfully. Confirm to the person in natural "
            "language that they're booked for a free trial, that a manager will "
            "reach out via the contact provided, and briefly say what happens next."
        ),
        "notify_title": "🔔 New lead — {business}",
        "notify_name": "Name",
        "notify_contact": "Contact",
        "notify_level": "Level",
        "notify_goal": "Goal",
        "notify_time": "Preferred time",
        "tool_description": (
            "Create a request for a free trial lesson at {business}. "
            "Call this ONLY when all five fields are known: name, contact (phone in "
            "international format +... or email), self-assessed level, learning goal "
            "and preferred time. If any field is missing, do not call the tool — "
            "politely ask for what's missing (one question at a time)."
        ),
    },
}


def labels(language: str) -> dict:
    return LABELS.get(language, LABELS["ru"])


def contacts_line_tmpl(language: str) -> str:
    return CONTACTS_LINE_TMPL.get(language, CONTACTS_LINE_TMPL["ru"])


def glue(language: str) -> dict:
    return GLUE.get(language, GLUE["ru"])
