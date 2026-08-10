/* ============================================================
   Verbo — клиентская логика чата.
   ============================================================ */
"use strict";

const LOGO_URL = "/assets/logo.png"; // если файла нет — тихо остаётся «V»

const I18N = {
  ru: {
    tagline: "Онлайн-школа английского · AI-консультант",
    heroTitle: "Чем могу помочь?",
    heroSub: "Спросите о ценах, форматах и расписании — или запишитесь на бесплатное пробное занятие.",
    servicesTitle: "Услуги и цены",
    inputPh: "Спросите о ценах или запишитесь на пробное занятие",
    disclaimer: "Verbo AI · отвечает по базе знаний школы",
    leadsTitle: "Заявки",
    leadsLoad: "Показать",
    passPh: "Пароль администратора",
    servicesMeta: (n) => (n ? `${n} услуг` : ""),
    waking: "Просыпаюсь после простоя, это займёт до минуты…",
    error: "Что-то пошло не так. Попробуйте ещё раз.",
    noLeads: "Заявок пока нет.",
    backName: (n) => `С возвращением, ${n}! Чем могу помочь дальше?`,
  },
  en: {
    tagline: "Online English school · AI assistant",
    heroTitle: "How can I help?",
    heroSub: "Ask about prices, formats and schedule — or book a free trial lesson.",
    servicesTitle: "Services & pricing",
    inputPh: "Ask about prices or book a trial lesson",
    disclaimer: "Verbo AI · answers from the school knowledge base",
    leadsTitle: "Leads",
    leadsLoad: "Show",
    passPh: "Admin password",
    servicesMeta: (n) => (n ? `${n} services` : ""),
    waking: "Waking up from sleep, this can take up to a minute…",
    error: "Something went wrong. Please try again.",
    noLeads: "No leads yet.",
    backName: (n) => `Welcome back, ${n}! How can I help?`,
  },
};

const ACTIONS = [
  { icon: "💰",
    ru: { label: "Цены и форматы", sub: "сколько стоит обучение", q: "Расскажите о ценах и форматах занятий" },
    en: { label: "Prices & formats", sub: "how much it costs", q: "Tell me about prices and lesson formats" } },
  { icon: "✍️",
    ru: { label: "Записаться на пробное", sub: "бесплатно, 30 минут", q: "Хочу записаться на бесплатное пробное занятие" },
    en: { label: "Book a trial", sub: "free, 30 minutes", q: "I want to book a free trial lesson" } },
  { icon: "🎯",
    ru: { label: "Подготовка к IELTS", sub: "курс и преподаватель", q: "Расскажите про подготовку к IELTS" },
    en: { label: "IELTS prep", sub: "course & teacher", q: "Tell me about IELTS preparation" } },
  { icon: "❄️",
    ru: { label: "Условия и заморозка", sub: "оплата, отмена, пауза", q: "Какие условия оплаты, отмены и заморозки занятий?" },
    en: { label: "Terms & freeze", sub: "payment, cancellation", q: "What are the payment, cancellation and freeze terms?" } },
];

const state = {
  sessionId: localStorage.getItem("verbo_sid") || "",
  lang: localStorage.getItem("verbo_lang") || "ru",
  services: [],
  hasLogo: true, // лого вписан прямо в HTML — аватары бота тоже используют его
  busy: false,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

/* ---------- i18n ---------- */
function applyLang() {
  const t = I18N[state.lang];
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => { if (t[n.dataset.i18n]) n.textContent = t[n.dataset.i18n]; });
  document.querySelectorAll("[data-i18n-ph]").forEach((n) => { if (t[n.dataset.i18nPh]) n.placeholder = t[n.dataset.i18nPh]; });
  $("#services-meta").textContent = t.servicesMeta(state.services.length);
  document.querySelectorAll(".lang__btn").forEach((b) => b.classList.toggle("is-active", b.dataset.lang === state.lang));
  renderActions();
}

/* ---------- Кнопки действий ---------- */
function renderActions() {
  const box = $("#actions");
  box.innerHTML = "";
  ACTIONS.forEach((a) => {
    const t = a[state.lang];
    const btn = el("button", "action"); btn.type = "button";
    btn.innerHTML =
      `<div class="action__icon">${a.icon}</div>` +
      `<div><div class="action__label">${t.label}</div><div class="action__sub">${t.sub}</div></div>`;
    btn.addEventListener("click", () => { $("#input").value = t.q; send(); });
    box.append(btn);
  });
}

/* ---------- Услуги ---------- */
function renderServices(services) {
  const inner = el("div", "card__body-inner");
  services.forEach((s) => {
    const row = el("div", "service");
    const left = el("div");
    const name = el("div", "service__name"); name.textContent = s.title;
    const meta = el("div", "service__meta"); meta.textContent = s.meta || "";
    left.append(name, meta);
    const price = el("div", "service__price"); price.textContent = s.price;
    row.append(left, price);
    inner.append(row);
  });
  const body = $("#services-body");
  body.innerHTML = "";
  body.append(inner);
}

/* ---------- Аккордеоны ---------- */
function initAccordions() {
  document.querySelectorAll(".card__head").forEach((head) =>
    head.addEventListener("click", () => head.closest(".card").classList.toggle("is-open"))
  );
}

/* ---------- Сообщения ---------- */
function botAvatar() {
  const av = el("div", "msg__avatar" + (state.hasLogo ? " has-img" : ""));
  av.innerHTML = state.hasLogo ? `<img src="${LOGO_URL}" alt="" />` : "V";
  return av;
}

function addMessage(role, text) {
  $("#hero").classList.add("is-hidden");
  const msg = el("div", `msg ${role === "user" ? "user" : "bot"}`);
  if (role !== "user") msg.append(botAvatar());
  const bubble = el("div", "bubble"); bubble.textContent = text;
  msg.append(bubble);
  $("#chat").append(msg);
  scrollDown();
  return bubble;
}

function addTyping() {
  const msg = el("div", "msg bot"); msg.id = "typing-msg";
  msg.append(botAvatar());
  const bubble = el("div", "bubble");
  bubble.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
  msg.append(bubble);
  $("#chat").append(msg);
  scrollDown();
  return msg;
}

function scrollDown() {
  const main = $("#main");
  requestAnimationFrame(() => { main.scrollTop = main.scrollHeight; });
}

/* ---------- Отправка ---------- */
async function send() {
  const input = $("#input");
  const text = input.value.trim();
  if (!text || state.busy) return;

  state.busy = true;
  $("#send").disabled = true;
  input.value = "";
  autoGrow();
  addMessage("user", text);

  const typing = addTyping();
  const wakeTimer = setTimeout(() => {
    const b = typing.querySelector(".bubble");
    if (b) b.textContent = I18N[state.lang].waking;
  }, 7000);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, message: text }),
    });
    const data = await res.json();
    if (data.session_id) { state.sessionId = data.session_id; localStorage.setItem("verbo_sid", data.session_id); }
    clearTimeout(wakeTimer);
    typing.remove();
    addMessage("bot", data.reply || I18N[state.lang].error);
  } catch (e) {
    clearTimeout(wakeTimer);
    typing.remove();
    addMessage("bot", I18N[state.lang].error);
  } finally {
    state.busy = false;
    $("#send").disabled = false;
    input.focus();
  }
}

/* ---------- Автоувеличение поля ---------- */
function autoGrow() {
  const input = $("#input");
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
}

/* ---------- Bootstrap ---------- */
async function bootstrap() {
  try {
    const url = "/api/bootstrap" + (state.sessionId ? `?session_id=${encodeURIComponent(state.sessionId)}` : "");
    const res = await fetch(url);
    const data = await res.json();

    state.sessionId = data.session_id;
    localStorage.setItem("verbo_sid", data.session_id);
    state.services = data.services || [];

    renderServices(state.services);
    applyLang();

    if (Array.isArray(data.history) && data.history.length) {
      data.history.forEach((m) => addMessage(m.role === "assistant" ? "bot" : "user", m.content));
      if (data.name) addMessage("bot", I18N[state.lang].backName(data.name));
    }
  } catch (e) {
    console.error("bootstrap failed", e);
    applyLang();
  }
}

/* ---------- Админ «Заявки» ---------- */
function initAdmin() {
  const modal = $("#admin-modal");
  // Панель заявок открывается только по адресу с #admin — для посетителей её нет.
  const sync = () => { modal.hidden = location.hash.toLowerCase() !== "#admin"; };
  const close = () => { modal.hidden = true; if (location.hash.toLowerCase() === "#admin") history.replaceState(null, "", location.pathname); };
  window.addEventListener("hashchange", sync);
  sync();
  $("#admin-close").addEventListener("click", close);
  modal.addEventListener("click", (e) => { if (e.target.id === "admin-modal") close(); });
  $("#admin-load").addEventListener("click", loadLeads);
}

async function loadLeads() {
  const status = $("#admin-status");
  const table = $("#admin-table");
  status.textContent = "…"; table.innerHTML = "";
  try {
    const res = await fetch("/api/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: $("#admin-pass").value }),
    });
    const data = await res.json();
    if (!res.ok) { status.textContent = data.error || "Ошибка"; return; }
    const leads = data.leads || [];
    status.textContent = `Заявок: ${leads.length}`;
    if (!leads.length) { table.innerHTML = `<div class="admin-status">${I18N[state.lang].noLeads}</div>`; return; }
    const cols = ["created_at", "name", "contact", "level", "goal", "preferred_time", "status"];
    const t = el("table");
    t.innerHTML = "<thead><tr>" + cols.map((c) => `<th>${c}</th>`).join("") + "</tr></thead>";
    const tb = el("tbody");
    leads.forEach((r) => {
      const tr = el("tr");
      tr.innerHTML = cols.map((c) => `<td>${(r[c] ?? "").toString().replace(/</g, "&lt;")}</td>`).join("");
      tb.append(tr);
    });
    t.append(tb); table.append(t);
  } catch (e) {
    status.textContent = "Ошибка сети";
  }
}

/* ---------- Инициализация ---------- */
function init() {
  initAccordions();
  initAdmin();

  $("#send").addEventListener("click", send);
  $("#input").addEventListener("input", autoGrow);
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });

  document.querySelectorAll(".lang__btn").forEach((b) =>
    b.addEventListener("click", () => {
      state.lang = b.dataset.lang;
      localStorage.setItem("verbo_lang", state.lang);
      applyLang();
    })
  );

  applyLang(); // мгновенно рисуем кнопки действий и тексты, не дожидаясь сервера
  bootstrap(); // догружает услуги/историю/сессию с сервера
}

document.addEventListener("DOMContentLoaded", init);
