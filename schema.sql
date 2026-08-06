-- ════════════════════════════════════════════════════════════════════════════
-- Verbo AI consultant — схема Supabase.
-- Выполнить в Supabase → SQL Editor. Создаёт таблицы leads, sessions, logs,
-- knowledge, включает RLS и НЕ создаёт публичных политик на чтение.
-- Доступ к данным — только с сервера по SERVICE_ROLE (обходит RLS).
-- ════════════════════════════════════════════════════════════════════════════

-- gen_random_uuid() доступен из расширения pgcrypto (в Supabase включено по умолчанию).
create extension if not exists pgcrypto;

-- ── Заявки ──────────────────────────────────────────────────────────────────
create table if not exists public.leads (
    id             uuid primary key default gen_random_uuid(),
    created_at     timestamptz not null default now(),
    name           text not null,
    contact        text not null,
    level          text,
    goal           text,
    preferred_time text,
    source         text not null default 'web-chat',
    session_id     text,
    status         text not null default 'new'
);

create index if not exists leads_created_at_idx on public.leads (created_at desc);
create index if not exists leads_session_idx    on public.leads (session_id);

-- ── Сессии (память диалога: профиль + история + резюме) ─────────────────────
create table if not exists public.sessions (
    id         text primary key,                 -- session_id (uuid4 из чата)
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    name       text,
    level      text,
    goal       text,
    format     text,
    budget     text,
    summary    text,
    history    jsonb not null default '[]'::jsonb, -- окно последних реплик
    greeted    boolean not null default false
);

-- Автообновление updated_at при любом апдейте строки сессии.
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists sessions_touch_updated_at on public.sessions;
create trigger sessions_touch_updated_at
    before update on public.sessions
    for each row execute function public.touch_updated_at();

-- ── Логи (вердикты судьи, ошибки, события роутера и инструментов) ────────────
create table if not exists public.logs (
    id         uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    session_id text,
    kind       text not null,                    -- 'judge' | 'error' | 'router' | 'tool'
    payload    jsonb not null default '{}'::jsonb
);

create index if not exists logs_created_at_idx on public.logs (created_at desc);
create index if not exists logs_kind_idx       on public.logs (kind);

-- ── База знаний (зеркало knowledge.py для аудита/правок) ─────────────────────
create table if not exists public.knowledge (
    id         uuid primary key default gen_random_uuid(),
    category   text not null,
    key        text not null,
    value      text not null,
    updated_at timestamptz not null default now(),
    unique (category, key)
);

-- ── RLS: включаем на всех таблицах, публичных политик на чтение НЕ создаём ────
-- SERVICE_ROLE обходит RLS, поэтому серверу политики не нужны. Анонимный ключ
-- (anon) без политик не получит доступа ни к чтению, ни к записи.
alter table public.leads     enable row level security;
alter table public.sessions  enable row level security;
alter table public.logs      enable row level security;
alter table public.knowledge enable row level security;

-- ВНИМАНИЕ: не добавляйте политик вида `for select using (true)` на leads/sessions/logs —
-- это открыло бы данные наружу. Если позже понадобится читать knowledge из клиента,
-- можно завести отдельную read-only политику ТОЛЬКО на public.knowledge.
