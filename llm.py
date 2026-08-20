# -*- coding: utf-8 -*-
"""
llm.py — тонкая обёртка над Google Gemini SDK (google-genai).

Здесь живут:
- with_retry() — единый механизм «таймаут + один ретрай» для всех внешних вызовов;
- to_contents() — перевод внутренней истории ({"role","content"}) в формат Gemini;
- generate() — вызов модели (с инструментами или без);
- complete_text() — получить простой текстовый ответ;
- complete_json() — получить строгий JSON (для роутера, судьи, извлечения профиля).

Никакого LangChain — только официальный SDK и ручной разбор ответа.

Замечание по ролям: внутри проекта историю храним в терминах "user"/"assistant"
(как удобно для памяти и Gradio), а Gemini ждёт "user"/"model" — конвертация
происходит в to_contents().
"""
import json
import time
import re
from typing import Callable, Any, Optional

from google.genai import types as gt

from config import gemini_client, log


def _is_transient(err: Exception) -> bool:
    """Перегрузка/лимит Gemini (503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, 500) —
    стоит подождать чуть дольше и повторить, а не сразу падать в заглушку."""
    s = str(err)
    return any(t in s for t in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500"))


def with_retry(fn: Callable[[], Any], *, what: str, retries: int = 3) -> Any:
    """
    Выполняет fn(); при исключении делает ещё `retries` попыток.
    На транзиентных ошибках Gemini (перегрузка/лимит) ждём заметно дольше, чтобы
    пережить короткий провал бэкенда, а не показать пользователю «technical glitch».
    Если все попытки исчерпаны — пробрасываем наверх.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — намеренно широкий перехват на внешней границе
            attempt += 1
            log.warning("Внешний вызов '%s' упал (попытка %d): %s", what, attempt, e)
            if attempt > retries:
                raise
            # Транзиентные — backoff до ~4с (переживаем блип, не вешая чат надолго);
            # прочие ошибки повторяем быстро.
            time.sleep((1.3 * attempt) if _is_transient(e) else (0.4 * attempt))


def to_contents(messages: list[dict]) -> list:
    """
    Переводит внутренние сообщения в contents Gemini.
    Каждый элемент messages: {"role": "user"|"assistant", "content": <str | list[Part]>}.
    Уже готовый gt.Content пропускаем как есть (используется в tool-loop).
    """
    contents = []
    for m in messages:
        if isinstance(m, gt.Content):
            contents.append(m)
            continue
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"]
        if isinstance(content, str):
            parts = [gt.Part(text=content)]
        else:
            parts = content  # уже список Part
        contents.append(gt.Content(role=role, parts=parts))
    return contents


def generate(
    *,
    model: str,
    system: str,
    contents: list,
    tools: Optional[list] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    json_mode: bool = False,
):
    """Единый вызов Gemini generate_content с таймаутом и одним ретраем."""
    config_kwargs: dict[str, Any] = {
        "system_instruction": system,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if tools:
        config_kwargs["tools"] = tools
        # Вызов инструментов крутим вручную (см. app._run_generation),
        # поэтому автоматический function calling отключаем.
        config_kwargs["automatic_function_calling"] = gt.AutomaticFunctionCallingConfig(
            disable=True
        )
    if json_mode:
        # Гарантируем валидный JSON для роутера/судьи/профиля.
        config_kwargs["response_mime_type"] = "application/json"

    cfg = gt.GenerateContentConfig(**config_kwargs)

    return with_retry(
        lambda: gemini_client.models.generate_content(
            model=model, contents=contents, config=cfg
        ),
        what=f"gemini:{model}",
    )


def text_from_response(response) -> str:
    """
    Достаёт текст из ответа Gemini. Устойчиво к случаю, когда в ответе есть
    только function_call-части (тогда response.text = None).
    """
    try:
        txt = response.text
        if txt:
            return txt.strip()
    except Exception:  # noqa: BLE001 — .text может ругаться, если текстовых частей нет
        pass

    parts_text = []
    for cand in (response.candidates or []):
        content = getattr(cand, "content", None)
        if not content:
            continue
        for p in (content.parts or []):
            if getattr(p, "text", None):
                parts_text.append(p.text)
    return "".join(parts_text).strip()


def function_calls(response) -> list:
    """Возвращает список вызовов инструментов из ответа (или пустой список)."""
    try:
        return list(response.function_calls or [])
    except Exception:  # noqa: BLE001
        return []


def complete_text(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> str:
    """Получить простой текстовый ответ модели."""
    response = generate(
        model=model,
        system=system,
        contents=to_contents(messages),
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return text_from_response(response)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_loose(raw: str) -> dict:
    """
    Достаёт JSON из ответа модели, даже если он обёрнут в markdown/текст.
    Кидает ValueError, если ничего распарсить не удалось.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_RE.search(raw)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Не удалось распарсить JSON из ответа модели: {raw!r}")


def complete_json(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 512,
    temperature: float = 0.0,
) -> dict:
    """
    Получить строгий JSON от модели. temperature=0 для детерминированности,
    response_mime_type=application/json для гарантии формата.
    """
    response = generate(
        model=model,
        system=system,
        contents=to_contents(messages),
        max_tokens=max_tokens,
        temperature=temperature,
        json_mode=True,
    )
    return parse_json_loose(text_from_response(response))
