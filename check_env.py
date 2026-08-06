# -*- coding: utf-8 -*-
"""
check_env.py — быстрая проверка готовности окружения перед запуском бота.

Проверяет:
  1) наличие обязательных переменных окружения;
  2) что ключ Gemini рабочий (реальный вызов модели);
  3) что Supabase доступен по SERVICE_ROLE и все нужные таблицы существуют.

Запуск:  python check_env.py
Код возврата 0 — всё готово, 1 — есть проблемы.
"""
import os
import sys

# Windows-консоль часто в cp1251/cp866 и падает на не-ASCII. Форсируем UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

REQUIRED = ["GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
OPTIONAL = ["ADMIN_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
TABLES = ["leads", "sessions", "logs", "knowledge"]


def _mask(v: str) -> str:
    if not v:
        return ""
    return v[:4] + "..." + v[-3:] if len(v) > 10 else "(задано)"


def main() -> int:
    ok = True

    print("== Переменные окружения ==")
    for k in REQUIRED:
        v = os.environ.get(k, "")
        print(f"  {k:30} {'[OK] ' + _mask(v) if v else '[НЕТ] ОТСУТСТВУЕТ'}")
        ok = ok and bool(v)
    for k in OPTIONAL:
        v = os.environ.get(k, "")
        print(f"  {k:30} {'[OK]' if v else '(пусто, необязательно)'}")

    # --- Gemini ---
    print("== Gemini ==")
    if not os.environ.get("GEMINI_API_KEY"):
        print("  [НЕТ] пропуск: нет GEMINI_API_KEY")
        ok = False
    else:
        try:
            from google import genai
            from google.genai import types as gt

            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            model = os.environ.get("GEMINI_MODEL_MAIN", "gemini-flash-latest")
            client.models.generate_content(
                model=model,
                contents="ответь одним словом: ок",
                config=gt.GenerateContentConfig(max_output_tokens=20, temperature=0),
            )
            print(f"  [OK] модель {model}: вызов прошёл")
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] вызов модели: {type(e).__name__}: {str(e)[:200]}")
            ok = False

    # --- Supabase ---
    print("== Supabase ==")
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("  [НЕТ] пропуск: нет SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
        ok = False
    else:
        try:
            from supabase import create_client

            sb = create_client(
                os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            )
            for t in TABLES:
                try:
                    sb.table(t).select("*").limit(1).execute()
                    print(f"  [OK]   таблица {t}")
                except Exception as e:  # noqa: BLE001
                    print(f"  [FAIL] таблица {t}: {str(e)[:160]}")
                    ok = False
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] подключение к Supabase: {type(e).__name__}: {str(e)[:200]}")
            ok = False

    print()
    print("ИТОГ:", "ВСЁ ГОТОВО" if ok else "ЕСТЬ ПРОБЛЕМЫ (см. выше)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
