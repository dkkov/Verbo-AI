/* ============================================================
   Verbo — клиентская логика чата.
   ============================================================ */
"use strict";

const I18N = {
  ru: {
    tagline: "Онлайн-школа английского · AI-консультант",
    heroTitle: "Чем могу помочь?",
    heroSub: "Спросите о ценах, форматах и расписании — или запишитесь на бесплатное пробное занятие.",
    servicesTitle: "Услуги и цены",
    examplesTitle: "Быстрые вопросы",
    examplesMeta: "примеры вопросов",
    inputPh: "Спросите о ценах, часах или запишитесь на пробное…",
    disclaimer: "Verbo AI · отвечает по базе знаний школы",
    leadsTitle: "Заявки",
    leadsLoad: "Показать",
    passPh: "Пароль администратора",
    servicesMeta: (n) => `${n} услуг`,
    waking: "Просыпаюсь после простоя, это займёт до минуты…",
    error: "Что-то пошло не так. Попробуйте ещё раз.",
    noLeads: "Заявок пока нет.",
  },
  en: {
    tagline: "Online English school · AI assistant",
    heroTitle: "How can I help?",
    heroSub: "Ask about prices, formats and schedule — or book a free trial lesson.",
    servicesTitle: "Services & pricing",
    examplesTitle: "Quick questions",
    examplesMeta: "example questions",
    inputPh: "Ask about prices, hours, or book a trial…",
    disclaimer: "Verbo AI · answers from the school knowledge base",
    leadsTitle: "Leads",
    leadsLoad: "Show",
    passPh: "Admin password",
    servicesMeta: (n) => `${n} services`,
    waking: "Waking up from sleep, this can take up to a minute…",
    error: "Something went wrong. Please try again.",
    noLeads: "No leads yet.",
  },
};

const state = {
  sessionId: localStorage.getItem("verbo_sid") || "",
  lang: localStorage.getItem("verbo_lang") || "ru",
  services: [],
  busy: false,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

/* ---------- i18n ---------- */
function applyLang() {
  const t = I18N[state.lang];
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => {
    const key = n.dataset.i18n;
    if (t[key]) n.textContent = t[key];
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((n) => {
    const key = n.dataset.i18nPh;
    if (t[key]) n.placeholder = t[key];
  });
  $("#services-meta").textContent = t.servicesMeta(state.services.length);
  document.querySelectorAll(".lang__btn").forEach((b) =>
    b.classList.toggle("is-active", b.dataset.lang === state.lang)
  );
}

/* ---------- Рендер услуг и примеров ---------- */
function renderServices(services) {
  const body = $("#services-body");
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
  body.innerHTML = "";
  body.append(inner);
}

function renderExamples(examples) {
  const body = $("#examples-body");
  const inner = el("div", "card__body-inner");
  const chips = el("div", "chips");
  examples.forEach((q) => {
    const chip = el("button", "chip"); chip.type = "button"; chip.textContent = q;
    chip.addEventListener("click", () => { $("#input").value = q; send(); });
    chips.append(chip);
  });
  inner.append(chips);
  body.innerHTML = "";
  body.append(inner);
}

/* ---------- Аккордеоны ---------- */
function initAccordions() {
  document.querySelectorAll(".card__head").forEach((head) => {
    head.addEventListener("click", () => head.closest(".card").classList.toggle("is-open"));
  });
}

/* ---------- Сообщения ---------- */
function addMessage(role, text) {
  $("#hero").classList.add("is-hidden");
  const msg = el("div", `msg ${role === "user" ? "user" : "bot"}`);
  const bubble = el("div", "bubble"); bubble.textContent = text;
  msg.append(bubble);
  $("#chat").append(msg);
  scrollDown();
  return bubble;
}

function addTyping() {
  const msg = el("div", "msg bot"); msg.id = "typing-msg";
  const bubble = el("div", "bubble");
  const dots = el("div", "typing");
  dots.innerHTML = "<span></span><span></span><span></span>";
  bubble.append(dots);
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
  // Подсказка про холодный старт, если ответ долго не приходит.
  const wakeTimer = setTimeout(() => {
    const b = typing.querySelector(".bubble");
    if (b) { b.innerHTML = ""; b.textContent = I18N[state.lang].waking; }
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
    renderExamples(data.examples || []);
    applyLang();

    // Восстанавливаем прошлый диалог.
    if (Array.isArray(data.history) && data.history.length) {
      data.history.forEach((m) => addMessage(m.role === "assistant" ? "bot" : "user", m.content));
      if (data.name) addMessage("bot", `С возвращением, ${data.name}! Чем могу помочь дальше?`);
    }
  } catch (e) {
    console.error("bootstrap failed", e);
    applyLang();
  }
}

/* ---------- Админ «Заявки» ---------- */
function initAdmin() {
  $("#admin-fab").addEventListener("click", () => $("#admin-modal").hidden = false);
  $("#admin-close").addEventListener("click", () => $("#admin-modal").hidden = true);
  $("#admin-modal").addEventListener("click", (e) => { if (e.target.id === "admin-modal") $("#admin-modal").hidden = true; });
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

  bootstrap();
}

document.addEventListener("DOMContentLoaded", init);
