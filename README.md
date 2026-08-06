# Verbo — AI-консультант онлайн-школы английского

Веб-чат на Gradio, который отвечает на вопросы о школе «Verbo», строго опираясь
на базу знаний, и записывает посетителей на бесплатное пробное занятие
(создаёт заявку в Supabase + уведомляет владельца в Telegram).

Стек: голый Python + официальный SDK Google Gemini (`google-genai`), Supabase (REST),
Gradio (веб-чат), FastAPI (`/health`), деплой на Render. Без LangChain/LlamaIndex —
роутинг, память и вызов инструментов реализованы вручную.

## Структура проекта

```
verbo-ai/
├── app.py            # оркестрация пайплайна + Gradio UI + FastAPI /health
├── router.py         # классификация намерений (PRICE/BOOKING/GENERAL/OFF_TOPIC)
├── tools.py          # инструмент create_lead: валидация, INSERT, Telegram
├── memory.py         # история + профиль + сворачивание в резюме (в Supabase)
├── judge.py          # самопроверка ответа перед отправкой
├── knowledge.py      # база знаний — единственный источник правды
├── db.py             # слой доступа к Supabase
├── llm.py            # обёртка над Gemini SDK: таймаут, ретрай, JSON-разбор
├── config.py         # переменные окружения и клиенты
├── prompts/          # текстовые промпты (system, router, judge, profile, summary)
├── schema.sql        # таблицы Supabase: leads, sessions, logs, knowledge (+ RLS)
├── requirements.txt
├── .env.example
├── render.yaml       # Render Blueprint
└── Procfile
```

## 1. Supabase

1. Создайте проект на [supabase.com](https://supabase.com).
2. Откройте **SQL Editor** и выполните весь `schema.sql`. Он создаст таблицы
   `leads`, `sessions`, `logs`, `knowledge`, включит RLS и НЕ создаст публичных
   политик на чтение (данные доступны только серверу по `SERVICE_ROLE`).
3. В **Project Settings → API** возьмите:
   - `SUPABASE_URL` (Project URL);
   - `SUPABASE_SERVICE_ROLE_KEY` (service_role secret — держите в тайне).

> **Почему приложение ходит в Supabase по REST, а не по прямому SQL.**
> Клиент supabase-py работает через PostgREST, который держит собственный пул
> соединений к Postgres на стороне Supabase — воркеры приложения прямых коннектов
> к базе не открывают и не упираются в их лимит. Поэтому приложению нужны только
> `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY`, а не строка подключения.
>
> Если понадобится прямой SQL (миграции, ручные запросы), используйте `DATABASE_URL`
> через Supavisor-пулер `*.pooler.supabase.com`: порт **5432** — session mode
> (удобно для миграций/psql), порт **6543** — transaction mode (для приложений
> с множеством коротких запросов). Пароль со спецсимволами percent-encode.

## 2. Telegram (уведомления о заявках)

1. Создайте бота у [@BotFather](https://t.me/BotFather) → получите `TELEGRAM_BOT_TOKEN`.
2. Напишите своему боту любое сообщение, затем откройте
   `https://api.telegram.org/bot<TOKEN>/getUpdates` и возьмите `chat.id` →
   это `TELEGRAM_CHAT_ID`.

Telegram не обязателен: если токен/chat_id не заданы, заявки всё равно сохраняются
в БД, просто без пуш-уведомления.

## 3. Локальный запуск

```bash
cd verbo-ai
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # затем впишите свои ключи
python app.py
```

Откроется на `http://localhost:7860`. Healthcheck — `http://localhost:7860/health`.

## 4. Переменные окружения

| Переменная                  | Обязательна | Назначение |
|-----------------------------|:-----------:|------------|
| `GEMINI_API_KEY`            | да          | Ключ к Gemini API (Google AI Studio) |
| `SUPABASE_URL`              | да          | URL проекта Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | да          | Серверный ключ (обходит RLS), только на сервере |
| `TELEGRAM_BOT_TOKEN`        | нет         | Токен бота для уведомлений |
| `TELEGRAM_CHAT_ID`          | нет         | Чат владельца для уведомлений |
| `ADMIN_PASSWORD`            | нет*        | Пароль вкладки «Заявки» (*без него вкладка закрыта) |
| `PORT`                      | нет         | Порт (Render задаёт сам; локально 7860) |
| `GEMINI_MODEL_MAIN`         | нет         | Основная модель (по умолч. `gemini-flash-latest`) |
| `GEMINI_MODEL_CHEAP`        | нет         | Модель роутера/судьи (по умолч. `gemini-flash-lite-latest`) |
| `CALL_TIMEOUT`              | нет         | Таймаут внешних вызовов, сек (по умолч. 30) |
| `HISTORY_WINDOW`            | нет         | Размер окна истории (по умолч. 12) |

## 5. Деплой на Render

**Вариант А — через Blueprint (`render.yaml`):** запушьте репозиторий на GitHub,
в Render нажмите **New → Blueprint**, укажите репозиторий. Затем впишите значения
секретов в **Environment**.

**Вариант Б — вручную:** **New → Web Service**, подключите репозиторий и задайте:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `python app.py`
- **Health check path:** `/health`
- **Environment:** переменные из таблицы выше.

Приложение слушает `0.0.0.0` и порт из `PORT` (Render задаёт его сам), `share=True`
не используется.

> **Холодный старт.** На тарифе free инстанс засыпает при простое; первый запрос
> после сна идёт долго. В чате на это время показывается индикатор «готовлю ответ…».
> Чтобы не засыпал — тариф starter (в `render.yaml`) или внешний пинг `/health`.

## Как это работает (кратко)

- **Роутер** классифицирует каждое сообщение (`router.py`) отдельным дешёвым
  вызовом модели со строгим JSON; при низкой уверенности — фолбэк на GENERAL.
- **Инструмент** `create_lead` (`tools.py`) вызывается моделью, только когда собраны
  все поля; контакт валидируется (телефон +380 или email), заявка пишется в
  `leads`, владельцу уходит уведомление в Telegram.
- **Память** (`memory.py`): окно последних 12 реплик + профиль (имя, уровень, цель,
  формат, бюджет) в Supabase по `session_id`; старая история сворачивается в резюме.
- **Судья** (`judge.py`) проверяет каждый ответ на соответствие базе знаний и тону;
  при провале — одна перегенерация. Вердикт пишется в `logs`, пользователю не виден.
- **Продолжение сессии:** откройте чат с `?sid=<session_id>` в URL — бот подхватит
  историю из Supabase и поздоровается по имени.
