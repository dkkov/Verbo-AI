# -*- coding: utf-8 -*-
"""
knowledge.py — ЕДИНСТВЕННЫЙ источник правды о школе «Verbo».

Всё, что бот имеет право утверждать как факт (цены, длительность, условия,
преподаватели, контакты), живёт здесь. Ничего сверх этого модель придумывать
не должна — за этим следит judge.py.

Структура специально плоская и человекочитаемая, чтобы менеджер школы мог
править её без знания Python. Функция render_knowledge() собирает из неё
текст, который подставляется в системный промпт.

Таблица Supabase `knowledge` — это ЗЕРКАЛО этого файла (для аудита и правок
из интерфейса). Синхронизация — db.sync_knowledge(). В рантайме промпт берёт
данные отсюда напрямую, чтобы не ходить в БД на каждый запрос.
"""

SCHOOL = {
    "name": "Verbo",
    "about": (
        "Онлайн-школа английского языка «Verbo». Работает с 2019 года, "
        "более 2400 выпускников."
    ),
    "schedule": "с 8:00 до 22:00 по Киеву, понедельник–суббота. Воскресенье — выходной.",
    "platform": "Zoom + личный кабинет с домашними заданиями и записями занятий.",
    "levels": "A1–C1.",
    "entry": (
        "Вход через бесплатный тест уровня (25 минут, онлайн) или пробное занятие."
    ),
    "trial": (
        "Пробное занятие: бесплатное, 30 минут, включает определение уровня "
        "и план обучения."
    ),
}

FORMATS = [
    {
        "key": "individual",
        "title": "Индивидуальные занятия",
        "duration": "50 минут",
        "price": "550 грн за занятие",
    },
    {
        "key": "mini_group",
        "title": "Мини-группы до 4 человек",
        "duration": "60 минут",
        "price": "320 грн за занятие",
    },
    {
        "key": "speaking_club",
        "title": "Разговорный клуб",
        "duration": "2 встречи в неделю",
        "price": "900 грн в месяц",
    },
]

PACKAGES = [
    {
        "key": "pack_8",
        "title": "Пакет 8 индивидуальных занятий",
        "price": "3960 грн",
        "note": "скидка 10%",
    },
    {
        "key": "pack_16",
        "title": "Пакет 16 индивидуальных занятий",
        "price": "7480 грн",
        "note": "скидка 15%",
    },
]

DIRECTIONS = [
    "General English",
    "Business English",
    "подготовка к IELTS",
    "английский для IT",
    "разговорная практика",
    "английский для детей 8–14 лет",
]

TEACHERS = [
    {
        "name": "Олена Ковальчук",
        "focus": "Business English, корпоративные группы",
        "experience": "8 лет опыта",
        "cert": "CELTA",
    },
    {
        "name": "Дмитрий Савченко",
        "focus": "подготовка к IELTS (собственный балл 8.0)",
        "experience": "6 лет опыта",
        "cert": "TKT",
    },
    {
        "name": "Мария Гринь",
        "focus": "дети и подростки, игровая методика",
        "experience": "5 лет опыта",
        "cert": "CELTA",
    },
    {
        "name": "Adam Price",
        "focus": "носитель языка (Великобритания), разговорная практика и произношение",
        "experience": "",
        "cert": "",
    },
    {
        "name": "Ирина Мельник",
        "focus": "методист школы, уровень C2, General English и внутренние аттестации",
        "experience": "",
        "cert": "",
    },
]

TEACHERS_SUMMARY = "Всего 12 преподавателей, все с CELTA или TKT."

POLICIES = {
    "payment": "Оплата помесячно или пакетами, карта / IBAN. Пакеты действуют 3 месяца.",
    "cancellation": (
        "Отмена занятия: не позднее чем за 12 часов, иначе занятие сгорает."
    ),
    "freeze": (
        "Заморозка: до 14 дней раз в полгода без потери оплаченных занятий."
    ),
    "refund": (
        "Возврат за неиспользованные занятия пакета — по заявлению, "
        "в течение 10 рабочих дней."
    ),
}

CONTACTS = {
    "phone": "+380 44 123 45 67",
    "email": "hello@verbo.school",
    "telegram": "@verbo_support",
}


def render_knowledge() -> str:
    """Собирает всю базу знаний в один текстовый блок для системного промпта."""
    lines = []
    lines.append(f"ШКОЛА: {SCHOOL['name']}")
    lines.append(SCHOOL["about"])
    lines.append("")

    lines.append("ФОРМАТЫ ЗАНЯТИЙ:")
    for f in FORMATS:
        lines.append(f"- {f['title']} — {f['duration']}, {f['price']}.")
    lines.append("")

    lines.append("ПАКЕТЫ:")
    for p in PACKAGES:
        lines.append(f"- {p['title']} — {p['price']} ({p['note']}).")
    lines.append("")

    lines.append(f"УРОВНИ: {SCHOOL['levels']}")
    lines.append(SCHOOL["entry"])
    lines.append(SCHOOL["trial"])
    lines.append("")

    lines.append(f"РАСПИСАНИЕ: {SCHOOL['schedule']}")
    lines.append(f"ПЛАТФОРМА: {SCHOOL['platform']}")
    lines.append("")

    lines.append("НАПРАВЛЕНИЯ: " + ", ".join(DIRECTIONS) + ".")
    lines.append("")

    lines.append("ПРЕПОДАВАТЕЛИ:")
    for t in TEACHERS:
        parts = [t["name"], "—", t["focus"]]
        tail = ", ".join(x for x in (t["experience"], t["cert"]) if x)
        line = f"- {t['name']} — {t['focus']}"
        if tail:
            line += f", {tail}"
        line += "."
        lines.append(line)
    lines.append(f"- {TEACHERS_SUMMARY}")
    lines.append("")

    lines.append("УСЛОВИЯ:")
    lines.append(f"- {POLICIES['payment']}")
    lines.append(f"- {POLICIES['cancellation']}")
    lines.append(f"- {POLICIES['freeze']}")
    lines.append(f"- {POLICIES['refund']}")
    lines.append("")

    lines.append("КОНТАКТЫ:")
    lines.append(f"- Телефон: {CONTACTS['phone']}")
    lines.append(f"- Email: {CONTACTS['email']}")
    lines.append(f"- Telegram: {CONTACTS['telegram']}")

    return "\n".join(lines)


def knowledge_rows() -> list[dict]:
    """
    Плоское представление базы знаний для зеркальной таблицы Supabase `knowledge`.
    Каждая строка: (category, key, value). Используется db.sync_knowledge().
    """
    rows = []
    rows.append({"category": "school", "key": "about", "value": SCHOOL["about"]})
    rows.append({"category": "school", "key": "schedule", "value": SCHOOL["schedule"]})
    rows.append({"category": "school", "key": "platform", "value": SCHOOL["platform"]})
    rows.append({"category": "school", "key": "levels", "value": SCHOOL["levels"]})
    rows.append({"category": "school", "key": "entry", "value": SCHOOL["entry"]})
    rows.append({"category": "school", "key": "trial", "value": SCHOOL["trial"]})

    for f in FORMATS:
        rows.append({
            "category": "format",
            "key": f["key"],
            "value": f"{f['title']} — {f['duration']}, {f['price']}.",
        })
    for p in PACKAGES:
        rows.append({
            "category": "package",
            "key": p["key"],
            "value": f"{p['title']} — {p['price']} ({p['note']}).",
        })
    rows.append({"category": "directions", "key": "all", "value": ", ".join(DIRECTIONS)})
    for i, t in enumerate(TEACHERS):
        tail = ", ".join(x for x in (t["experience"], t["cert"]) if x)
        value = f"{t['name']} — {t['focus']}"
        if tail:
            value += f", {tail}"
        rows.append({"category": "teacher", "key": f"teacher_{i}", "value": value})
    for k, v in POLICIES.items():
        rows.append({"category": "policy", "key": k, "value": v})
    for k, v in CONTACTS.items():
        rows.append({"category": "contact", "key": k, "value": v})
    return rows


# Готовый текст базы знаний. Считается один раз при импорте модуля.
KNOWLEDGE_TEXT = render_knowledge()

# Короткая строка контактов — используется в фолбэках при ошибках инструментов.
CONTACTS_LINE = (
    f"Телефон {CONTACTS['phone']}, email {CONTACTS['email']}, "
    f"Telegram {CONTACTS['telegram']}."
)
