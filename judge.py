# -*- coding: utf-8 -*-
"""
judge.py — самопроверка ответа перед отправкой.

Второй вызов модели проверяет черновик по критериям: факты сверены с базой знаний,
нет выдуманных скидок/гарантий, тон дружелюбный и в пределах 5 предложений.
Вердикт логируется в Supabase (logs), пользователю не показывается.
"""
from config import MODEL_CHEAP
from llm import complete_json
from knowledge import KNOWLEDGE_TEXT
import business
import strings
import prompts
import db

_GLUE = strings.glue(business.LANGUAGE)


def review(answer: str, session_id: str) -> dict:
    """
    Проверяет черновик ответа. Возвращает {"pass": bool, "issues": [...]}.
    Вердикт пишет в logs. При сбое самого судьи — пропускаем ответ (fail-open),
    чтобы техническая ошибка судьи не блокировала диалог.
    """
    system = prompts.get("judge").format(
        knowledge=KNOWLEDGE_TEXT,
        answer=answer,
    )
    try:
        verdict = complete_json(
            model=MODEL_CHEAP,
            system=system,
            messages=[{"role": "user", "content": _GLUE["judge_user"]}],
            max_tokens=400,
        )
    except Exception as e:  # noqa: BLE001
        db.insert_log(session_id, "error", {"where": "judge", "error": str(e)})
        return {"pass": True, "issues": [], "degraded": True}

    passed = bool(verdict.get("pass", True))
    issues = verdict.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]

    db.insert_log(
        session_id,
        "judge",
        {"pass": passed, "issues": issues, "answer_preview": answer[:500]},
    )
    return {"pass": passed, "issues": issues}


def issues_as_feedback(issues: list[str]) -> str:
    """Формирует текст замечаний судьи для перегенерации ответа."""
    bullet = "\n".join(f"- {i}" for i in issues)
    return _GLUE["judge_feedback"].format(issues=bullet)
