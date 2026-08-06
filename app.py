# -*- coding: utf-8 -*-
"""
app.py — оркестрация ответа и веб-чат на Gradio.

Пайплайн одного сообщения:
  1. извлекаем/обновляем профиль из реплики пользователя (чтобы не переспрашивать);
  2. классифицируем намерение (router);
  3. генерируем ответ основной моделью (для BOOKING — с инструментом create_lead);
  4. прогоняем ответ через судью (judge); при провале — одна перегенерация;
  5. сохраняем реплики в память (Supabase);
  6. стримим финальный, уже проверенный ответ в UI.

Интерфейс: gr.Blocks с двумя вкладками — «Чат» и «Заявки» (под паролем).
Развёртывание: FastAPI c /health, Gradio примонтирован на «/», слушаем 0.0.0.0:PORT.
"""
import time
import uuid

import pandas as pd
import gradio as gr
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from google.genai import types as gt

import config
from config import log, MODEL_MAIN
from knowledge import KNOWLEDGE_TEXT, CONTACTS_LINE, knowledge_rows
import prompts
import memory
import router
import judge
import db
from tools import build_create_lead_tool, run_create_lead
from llm import generate, text_from_response, to_contents, function_calls

# --------------------------------------------------------------------------- #
# Константы интерфейса                                                        #
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
        # Добавляем ход модели (с function_call) в историю запроса.
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

        # Возвращаем модели результат инструмента и просим финальный ответ.
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

    # 1. Профиль: извлекаем новое из реплики, чтобы не переспрашивать известное.
    profile = memory.update_profile(session_id, ctx["profile"], user_message)

    # 2. Роутер.
    routing = router.classify(ctx["history"], user_message)
    intent = routing["intent"]
    db.insert_log(session_id, "router", routing)

    # 3. Контекст для модели: окно истории + текущая реплика.
    model_messages = list(ctx["history"]) + [{"role": "user", "content": user_message}]
    system = build_system_prompt(profile, ctx["summary"])

    # 4. Черновик.
    draft = _run_generation(session_id, intent, system, model_messages, allow_tools=True)

    # 5. Судья. При провале — ровно одна перегенерация с замечаниями.
    verdict = judge.review(draft, session_id)
    final = draft
    if not verdict["pass"] and verdict.get("issues"):
        feedback = judge.issues_as_feedback(verdict["issues"])
        regen_messages = model_messages + [
            {"role": "assistant", "content": draft},
            {"role": "user", "content": feedback},
        ]
        # На перегенерации инструменты не нужны: заявка (если была) уже создана.
        final = _run_generation(
            session_id, intent, system, regen_messages, allow_tools=False
        )
        judge.review(final, session_id)  # логируем второй вердикт, но цикл не повторяем

    # 6. Память: сохраняем обе реплики.
    memory.append_message(session_id, "user", user_message)
    memory.append_message(session_id, "assistant", final)
    return final


# --------------------------------------------------------------------------- #
# Gradio: обработчики чата                                                     #
# --------------------------------------------------------------------------- #
def _stream_chunks(text: str):
    """Разбивает готовый текст на кусочки для эффекта стриминга в UI."""
    words = text.split(" ")
    for i in range(0, len(words), 3):
        yield " ".join(words[: i + 3])


def add_user_message(user_msg: str, history: list[dict]):
    """Добавляет реплику пользователя в чат и очищает поле ввода."""
    if not user_msg or not user_msg.strip():
        return "", history
    history = history + [{"role": "user", "content": user_msg.strip()}]
    return "", history


def bot_respond(history: list[dict], session_id: str):
    """
    Генератор ответа бота со стримингом. Сначала показывает индикатор
    (важно для холодного старта Render), затем стримит проверенный ответ.
    """
    if not history or history[-1]["role"] != "user":
        yield history
        return

    user_msg = history[-1]["content"]

    # Индикатор обработки (первый запрос после простоя может идти долго).
    history = history + [{"role": "assistant", "content": "⏳ Секунду, готовлю ответ…"}]
    yield history

    try:
        final = generate_reply(session_id, user_msg)
    except Exception as e:  # noqa: BLE001 — внешняя граница: пользователю человеческий текст
        log.error("Сбой генерации ответа: %s", e)
        db.insert_log(session_id, "error", {"where": "generate_reply", "error": str(e)})
        final = ERROR_REPLY

    for partial in _stream_chunks(final):
        history[-1]["content"] = partial
        yield history
        time.sleep(0.02)

    history[-1]["content"] = final
    yield history


def hydrate(request: gr.Request):
    """
    Инициализация при загрузке страницы. Если в URL есть ?sid=<id> — продолжаем
    ту же сессию (память в Supabase), иначе создаём новую. Возвращающегося
    пользователя приветствуем по имени.
    """
    sid = None
    if request is not None:
        sid = request.query_params.get("sid")
    if not sid:
        sid = str(uuid.uuid4())

    prior = memory.full_history(sid)
    if prior:
        display = [{"role": m["role"], "content": m["content"]} for m in prior]
        ctx = memory.load_context(sid)
        if ctx["name"]:
            display.append(
                {
                    "role": "assistant",
                    "content": (
                        f"С возвращением, {ctx['name']}! Продолжим с того же места — "
                        "чем могу помочь?"
                    ),
                }
            )
    else:
        display = [{"role": "assistant", "content": GREETING}]

    return display, sid


def reset_chat():
    """«Начать заново»: новая сессия и чистый чат. Заявки в БД не трогаем."""
    new_sid = str(uuid.uuid4())
    return [{"role": "assistant", "content": GREETING}], new_sid


# --------------------------------------------------------------------------- #
# Gradio: вкладка «Заявки» (под паролем)                                       #
# --------------------------------------------------------------------------- #
_LEADS_COLUMNS = [
    "created_at", "name", "contact", "level", "goal", "preferred_time", "status", "session_id",
]


def load_leads(password: str):
    """Показывает таблицу leads, если введён верный ADMIN_PASSWORD."""
    if not config.ADMIN_PASSWORD:
        return pd.DataFrame(columns=_LEADS_COLUMNS), "ADMIN_PASSWORD не настроен на сервере."
    if password != config.ADMIN_PASSWORD:
        return pd.DataFrame(columns=_LEADS_COLUMNS), "Неверный пароль."
    try:
        rows = db.list_leads()
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось загрузить заявки: %s", e)
        return pd.DataFrame(columns=_LEADS_COLUMNS), "Ошибка загрузки заявок из БД."

    df = pd.DataFrame(rows, columns=_LEADS_COLUMNS) if rows else pd.DataFrame(columns=_LEADS_COLUMNS)
    return df, f"Загружено заявок: {len(rows)}"


# --------------------------------------------------------------------------- #
# Сборка интерфейса                                                           #
# --------------------------------------------------------------------------- #
def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Verbo — консультант", theme=gr.themes.Soft()) as demo:
        session_state = gr.State(value=None)

        with gr.Tab("Чат"):
            gr.Markdown("## Verbo — онлайн-школа английского\nЗадайте вопрос или запишитесь на бесплатное пробное занятие.")
            chatbot = gr.Chatbot(
                type="messages",
                height=460,
                label="Диалог",
                avatar_images=(None, None),
            )
            with gr.Row():
                msg = gr.Textbox(
                    placeholder="Напишите сообщение…",
                    show_label=False,
                    scale=8,
                    autofocus=True,
                )
                send_btn = gr.Button("Отправить", variant="primary", scale=1)
            with gr.Row():
                reset_btn = gr.Button("Начать заново")
            gr.Examples(examples=EXAMPLES, inputs=msg, label="Примеры вопросов")

            # Отправка по Enter и по кнопке — один и тот же сценарий.
            submit_args = dict(
                fn=add_user_message, inputs=[msg, chatbot], outputs=[msg, chatbot], queue=False
            )
            msg.submit(**submit_args).then(
                bot_respond, [chatbot, session_state], chatbot
            )
            send_btn.click(**submit_args).then(
                bot_respond, [chatbot, session_state], chatbot
            )

            reset_btn.click(reset_chat, outputs=[chatbot, session_state], queue=False)

        with gr.Tab("Заявки"):
            gr.Markdown("### Заявки (leads)\nДоступ по паролю.")
            with gr.Row():
                pwd = gr.Textbox(
                    placeholder="Пароль администратора",
                    type="password",
                    show_label=False,
                    scale=6,
                )
                load_btn = gr.Button("Показать заявки", variant="primary", scale=1)
            leads_status = gr.Markdown("")
            leads_table = gr.Dataframe(
                headers=_LEADS_COLUMNS, interactive=False, wrap=True, label="Заявки"
            )
            load_btn.click(load_leads, inputs=pwd, outputs=[leads_table, leads_status])

        # Инициализация при загрузке страницы (гидратация сессии).
        demo.load(hydrate, inputs=None, outputs=[chatbot, session_state])

    return demo


# --------------------------------------------------------------------------- #
# FastAPI + монтирование Gradio + /health                                     #
# --------------------------------------------------------------------------- #
app = FastAPI(title="Verbo AI consultant")


@app.get("/health")
def health():
    """Лёгкий healthcheck для Render — всегда 200, не завязан на внешние сервисы."""
    return JSONResponse({"status": "ok"})


demo = build_demo()
demo.queue()  # включаем очередь: нужна для стриминга и параллельных пользователей
app = gr.mount_gradio_app(app, demo, path="/")


def _sync_knowledge_best_effort():
    """При старте зеркалим базу знаний в таблицу knowledge (не критично)."""
    try:
        db.sync_knowledge(knowledge_rows())
        log.info("База знаний синхронизирована в таблицу knowledge.")
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось синхронизировать knowledge (не критично): %s", e)


if __name__ == "__main__":
    import uvicorn

    _sync_knowledge_best_effort()
    log.info("Запуск Verbo на 0.0.0.0:%s", config.PORT)
    # Слушаем 0.0.0.0 и порт из окружения (Render задаёт PORT). Без share=True.
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
