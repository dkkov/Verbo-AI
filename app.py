# -*- coding: utf-8 -*-
"""
app.py — оркестрация ответа + HTTP-слой (FastAPI) и кастомный веб-фронтенд.

Пайплайн одного сообщения (не зависит от интерфейса):
  1. извлекаем/обновляем профиль из реплики (чтобы не переспрашивать);
  2. классифицируем намерение (router);
  3. генерируем ответ основной моделью (для BOOKING — с инструментом create_lead);
  4. прогоняем ответ через судью (judge); при провале — одна перегенерация;
  5. сохраняем реплики в память (Supabase);
  6. отдаём финальный, уже проверенный ответ.

Интерфейс — собственный SPA в папке web/ (индиго, тёмная тема), общается с
бэкендом по JSON API. Развёртывание: FastAPI, /health, слушаем 0.0.0.0:PORT.
"""
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.genai import types as gt

import config
from config import log, MODEL_MAIN
from knowledge import KNOWLEDGE_TEXT, CONTACTS_LINE, knowledge_rows, FORMATS, PACKAGES
import prompts
import memory
import router
import judge
import db
from tools import build_create_lead_tool, run_create_lead
from llm import generate, text_from_response, to_contents, function_calls

# --------------------------------------------------------------------------- #
# Контент интерфейса                                                          #
# --------------------------------------------------------------------------- #
EXAMPLES = [
    "Сколько стоит индивидуальное занятие?",
    "Хочу записаться на пробное",
    "Готовите к IELTS?",
    "Можно ли заморозить пакет?",
]

GREETING = (
    "Здравствуйте! Я консультант онлайн-школы английского «Verbo». "
    "Помогу разобраться с форматами и ценами, отвечу на вопросы о школе "
    "и запишу на бесплатное пробное занятие. Что вас интересует?"
)

ERROR_REPLY = (
    "Извините, у меня возникла техническая заминка. Попробуйте, пожалуйста, "
    "написать ещё раз чуть позже или свяжитесь со школой напрямую: " + CONTACTS_LINE
)

MAX_TOOL_ITERATIONS = 3


# --------------------------------------------------------------------------- #
# Сборка системного промпта                                                   #
# --------------------------------------------------------------------------- #
def build_system_prompt(profile: dict, summary: str) -> str:
    return prompts.get("system").format(
        profile=memory.format_profile(profile),
        summary=summary or "(беседа только началась)",
        knowledge=KNOWLEDGE_TEXT,
    )


# --------------------------------------------------------------------------- #
# Генерация ответа (с ручным tool-loop для BOOKING)                            #
# --------------------------------------------------------------------------- #
def _run_generation(
    session_id: str,
    intent: str,
    system: str,
    messages: list[dict],
    allow_tools: bool = True,
) -> str:
    """
    Один проход генерации основной моделью. Для BOOKING включаем инструмент
    create_lead и вручную крутим цикл function_call → function_response →
    финальный текст (Gemini function calling).
    """
    tools = [build_create_lead_tool()] if (intent == "BOOKING" and allow_tools) else None

    contents = to_contents(messages)
    response = generate(
        model=MODEL_MAIN,
        system=system,
        contents=contents,
        tools=tools,
        max_tokens=700,
        temperature=0.4,
    )

    iterations = 0
    while tools and function_calls(response) and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        contents.append(response.candidates[0].content)

        response_parts = []
        for fc in function_calls(response):
            if fc.name == "create_lead":
                result = run_create_lead(dict(fc.args), session_id)
            else:
                result = {"status": "error", "message": "Неизвестный инструмент."}
            response_parts.append(
                gt.Part.from_function_response(name=fc.name, response=result)
            )

        contents.append(gt.Content(role="user", parts=response_parts))
        response = generate(
            model=MODEL_MAIN,
            system=system,
            contents=contents,
            tools=tools,
            max_tokens=700,
            temperature=0.4,
        )

    return text_from_response(response)


def generate_reply(session_id: str, user_message: str) -> str:
    """
    Полный пайплайн: профиль → роутер → генерация → судья → память.
    Возвращает финальный, уже проверенный текст ответа.
    """
    ctx = memory.load_context(session_id)

    profile = memory.update_profile(session_id, ctx["profile"], user_message)

    routing = router.classify(ctx["history"], user_message)
    intent = routing["intent"]
    db.insert_log(session_id, "router", routing)

    model_messages = list(ctx["history"]) + [{"role": "user", "content": user_message}]
    system = build_system_prompt(profile, ctx["summary"])

    draft = _run_generation(session_id, intent, system, model_messages, allow_tools=True)

    verdict = judge.review(draft, session_id)
    final = draft
    if not verdict["pass"] and verdict.get("issues"):
        feedback = judge.issues_as_feedback(verdict["issues"])
        regen_messages = model_messages + [
            {"role": "assistant", "content": draft},
            {"role": "user", "content": feedback},
        ]
        final = _run_generation(
            session_id, intent, system, regen_messages, allow_tools=False
        )
        judge.review(final, session_id)

    memory.append_message(session_id, "user", user_message)
    memory.append_message(session_id, "assistant", final)
    return final


# --------------------------------------------------------------------------- #
# Данные для интерфейса из базы знаний (единый источник правды)                #
# --------------------------------------------------------------------------- #
def _services_payload() -> list[dict]:
    """Список услуг с ценами для аккордеона «Услуги и цены»."""
    services = [
        {"title": f["title"], "meta": f["duration"], "price": f["price"]}
        for f in FORMATS
    ]
    services += [
        {"title": p["title"], "meta": p["note"], "price": p["price"]}
        for p in PACKAGES
    ]
    return services


# --------------------------------------------------------------------------- #
# FastAPI                                                                      #
# --------------------------------------------------------------------------- #
def _sync_knowledge_best_effort():
    try:
        db.sync_knowledge(knowledge_rows())
        log.info("База знаний синхронизирована в таблицу knowledge.")
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось синхронизировать knowledge (не критично): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _sync_knowledge_best_effort()
    yield


app = FastAPI(title="Verbo AI consultant", lifespan=lifespan)


@app.middleware("http")
async def no_cache_for_pages(request, call_next):
    """
    HTML/CSS/JS отдаём с no-cache, чтобы после деплоя браузер всегда брал
    свежую версию (через revalidation), а не показывал старую из кэша.
    Шрифты/картинки кэшируются как обычно — они меняются редко.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".css", ".js")):
        response.headers["Cache-Control"] = "no-cache"
    return response


WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class ChatIn(BaseModel):
    session_id: str
    message: str


class LeadsIn(BaseModel):
    password: str


@app.get("/health")
def health():
    """Лёгкий healthcheck для Render — всегда 200, не завязан на внешние сервисы."""
    return JSONResponse({"status": "ok"})


@app.get("/api/bootstrap")
def bootstrap(session_id: str | None = None):
    """
    Инициализация клиента: выдаёт (или создаёт) session_id, историю прошлого
    диалога, приветствие, список услуг и примеры вопросов.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    ctx = memory.load_context(session_id)
    history = [
        {"role": m["role"], "content": m["content"]} for m in memory.full_history(session_id)
    ]

    return {
        "session_id": session_id,
        "name": ctx.get("name") or "",
        "returning": bool(history),
        "greeting": GREETING,
        "history": history,
        "services": _services_payload(),
        "examples": EXAMPLES,
    }


# Сообщения обрабатываем в СИНХРОННОМ эндпоинте: FastAPI выполнит его в пуле
# потоков, чтобы блокирующие вызовы модели/БД не останавливали event loop.
@app.post("/api/chat")
def chat(body: ChatIn):
    session_id = body.session_id or str(uuid.uuid4())
    message = (body.message or "").strip()
    if not message:
        return {"reply": "", "session_id": session_id}

    try:
        reply = generate_reply(session_id, message)
    except Exception as e:  # noqa: BLE001 — внешняя граница: пользователю человеческий текст
        log.error("Сбой генерации ответа: %s", e)
        db.insert_log(session_id, "error", {"where": "chat", "error": str(e)})
        reply = ERROR_REPLY

    return {"reply": reply, "session_id": session_id}


@app.post("/api/leads")
def leads(body: LeadsIn):
    """Заявки для админ-панели — только при верном ADMIN_PASSWORD."""
    if not config.ADMIN_PASSWORD:
        return JSONResponse(
            {"error": "ADMIN_PASSWORD не настроен на сервере."}, status_code=403
        )
    if body.password != config.ADMIN_PASSWORD:
        return JSONResponse({"error": "Неверный пароль."}, status_code=401)
    try:
        return {"leads": db.list_leads()}
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось загрузить заявки: %s", e)
        return JSONResponse({"error": "Ошибка загрузки заявок."}, status_code=500)


# Корректный MIME для шрифтов (иначе StaticFiles отдаёт woff2 как text/plain).
import mimetypes  # noqa: E402

mimetypes.add_type("font/woff2", ".woff2")

# Статический фронтенд монтируем ПОСЛЕДНИМ, чтобы /health и /api/* имели приоритет.
# html=True отдаёт index.html на "/" и обслуживает style.css / app.js.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    _sync_knowledge_best_effort()
    log.info("Запуск Verbo на 0.0.0.0:%s", config.PORT)
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
