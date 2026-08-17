# -*- coding: utf-8 -*-
"""
test_prompts.py — проверка загрузчика промптов и их .format() без секретов/сети.
Запуск: SCHOOL_CONFIG=configs/<...>.yaml python test_prompts.py
Ловит битые фигурные скобки и отсутствующие файлы промптов.
"""
import os
import business
import prompts
from knowledge import KNOWLEDGE_TEXT

lang = business.LANGUAGE
print(f"language = {lang}")

# router загружается «как есть» (без .format).
router = prompts.get("router")
assert "PRICE" in router and "BOOKING" in router

# system.md — подстановка profile/summary/knowledge.
system = prompts.get("system").format(profile="{}", summary="", knowledge=KNOWLEDGE_TEXT)
assert "create_lead" in system

# judge.md — подстановка knowledge/answer.
judge = prompts.get("judge").format(knowledge=KNOWLEDGE_TEXT, answer="test draft")
assert '"pass"' in judge  # литеральный JSON {{ }} должен схлопнуться в { }

# profile.md — подстановка profile/message.
profile = prompts.get("profile").format(profile="{}", message="hi")
assert '"name"' in profile

# summary.md — подстановка summary/old_messages.
summary = prompts.get("summary").format(summary="", old_messages="[]")
assert len(summary) > 20

# Язык промптов соответствует конфигу.
if lang == "en":
    assert "You are the AI assistant" in system
    assert "грн" not in system and "Ты —" not in system
else:
    assert "Ты — AI-консультант" in system

print("PASSED: промпты грузятся и форматируются без ошибок")
