# -*- coding: utf-8 -*-
"""
knowledge.py — ЕДИНСТВЕННЫЙ источник правды о школе.

Раньше данные были захардкожены здесь. Теперь они приходят из конфига активной
школы (business.py ← configs/<tenant>.yaml), а этот модуль лишь собирает из них
текст базы знаний для системного промпта и «плоское» представление для зеркальной
таблицы Supabase `knowledge`. Ярлыки разделов — язык-зависимые (strings.py).

Публичный API (SCHOOL, FORMATS, PACKAGES, ..., render_knowledge, knowledge_rows,
KNOWLEDGE_TEXT, CONTACTS_LINE) сохранён, чтобы остальной код не менялся.
"""
import business
import strings

# Реэкспорт данных активной школы под прежними именами (совместимость).
SCHOOL = business.BUSINESS
FORMATS = business.FORMATS
PACKAGES = business.PACKAGES
DIRECTIONS = business.DIRECTIONS
TEACHERS = business.TEACHERS
TEACHERS_SUMMARY = business.TEACHERS_SUMMARY
POLICIES = business.POLICIES
CONTACTS = business.CONTACTS

_L = strings.labels(business.LANGUAGE)


def render_knowledge() -> str:
    """Собирает всю базу знаний в один текстовый блок для системного промпта."""
    lines = []
    lines.append(f"{_L['school']}: {SCHOOL['name']}")
    lines.append(SCHOOL["about"])
    lines.append("")

    lines.append(_L["formats_header"])
    for f in FORMATS:
        lines.append(f"- {f['title']} — {f['duration']}, {f['price']}.")
    lines.append("")

    lines.append(_L["packages_header"])
    for p in PACKAGES:
        lines.append(f"- {p['title']} — {p['price']} ({p['note']}).")
    lines.append("")

    lines.append(f"{_L['levels']}: {SCHOOL['levels']}")
    lines.append(SCHOOL["entry"])
    lines.append(SCHOOL["trial"])
    lines.append("")

    lines.append(f"{_L['schedule']}: {SCHOOL['schedule']}")
    lines.append(f"{_L['platform']}: {SCHOOL['platform']}")
    lines.append("")

    lines.append(f"{_L['directions']}: " + ", ".join(DIRECTIONS) + ".")
    lines.append("")

    lines.append(_L["teachers_header"])
    for t in TEACHERS:
        line = f"- {t['name']} — {t['focus']}"
        tail = ", ".join(x for x in (t.get("experience", ""), t.get("cert", "")) if x)
        if tail:
            line += f", {tail}"
        line += "."
        lines.append(line)
    lines.append(f"- {TEACHERS_SUMMARY}")
    lines.append("")

    lines.append(_L["policies_header"])
    lines.append(f"- {POLICIES['payment']}")
    lines.append(f"- {POLICIES['cancellation']}")
    lines.append(f"- {POLICIES['freeze']}")
    lines.append(f"- {POLICIES['refund']}")
    lines.append("")

    lines.append(_L["contacts_header"])
    lines.append(f"- {_L['phone']}: {CONTACTS['phone']}")
    lines.append(f"- {_L['email']}: {CONTACTS['email']}")
    lines.append(f"- {_L['telegram']}: {CONTACTS['telegram']}")

    return "\n".join(lines)


def knowledge_rows() -> list[dict]:
    """
    Плоское представление базы знаний для зеркальной таблицы Supabase `knowledge`.
    Каждая строка: (category, key, value). Используется db.sync_knowledge().
    """
    rows = []
    for key in ("about", "schedule", "platform", "levels", "entry", "trial"):
        rows.append({"category": "school", "key": key, "value": SCHOOL[key]})

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
        tail = ", ".join(x for x in (t.get("experience", ""), t.get("cert", "")) if x)
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
CONTACTS_LINE = strings.contacts_line_tmpl(business.LANGUAGE).format(
    phone=CONTACTS["phone"],
    email=CONTACTS["email"],
    telegram=CONTACTS["telegram"],
)
