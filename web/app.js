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

// SVG-иконки (Lucide, единый stroke 2px) вместо эмодзи — консистентны на всех платформах.
const _svg = (p) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const ICONS = {
  wallet: _svg('<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/>'),
  calendar: _svg('<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>'),
  cap: _svg('<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>'),
  snowflake: _svg('<line x1="2" x2="22" y1="12" y2="12"/><line x1="12" x2="12" y1="2" y2="22"/><path d="m20 16-4-4 4-4"/><path d="m4 8 4 4-4 4"/><path d="m16 4-4 4-4-4"/><path d="m8 20 4-4 4 4"/>'),
};

const ACTIONS = [
  { icon: ICONS.wallet,
    ru: { label: "Цены и форматы", sub: "сколько стоит обучение", q: "Расскажите о ценах и форматах занятий" },
    en: { label: "Prices & formats", sub: "how much it costs", q: "Tell me about prices and lesson formats" } },
  { icon: ICONS.calendar,
    ru: { label: "Записаться на пробное", sub: "бесплатно, 30 минут", q: "Хочу записаться на бесплатное пробное занятие" },
    en: { label: "Book a trial", sub: "free, 30 minutes", q: "I want to book a free trial lesson" } },
  { icon: ICONS.cap,
    ru: { label: "Подготовка к IELTS", sub: "курс и преподаватель", q: "Расскажите про подготовку к IELTS" },
    en: { label: "IELTS prep", sub: "course & teacher", q: "Tell me about IELTS preparation" } },
  { icon: ICONS.snowflake,
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

/* ---------- Голосовой ввод ---------- */
const rec = { recording: false, mr: null, chunks: [], stream: null };

async function toggleMic() {
  if (state.busy) return;
  if (rec.recording) { stopMic(); return; }
  try {
    rec.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    rec.chunks = [];
    rec.mr = new MediaRecorder(rec.stream);
    rec.mr.ondataavailable = (e) => { if (e.data && e.data.size) rec.chunks.push(e.data); };
    rec.mr.onstop = onRecStop;
    rec.mr.start();
    rec.recording = true;
    $("#mic").classList.add("is-recording");
  } catch (e) {
    addMessage("bot", "Не удалось получить доступ к микрофону — разрешите его в браузере и попробуйте снова.");
  }
}

function stopMic() {
  if (rec.mr && rec.recording) {
    rec.recording = false;
    $("#mic").classList.remove("is-recording");
    rec.mr.stop();
  }
}

async function onRecStop() {
  if (rec.stream) rec.stream.getTracks().forEach((t) => t.stop());
  const blob = new Blob(rec.chunks, { type: rec.chunks[0] ? rec.chunks[0].type : "audio/webm" });
  if (blob.size < 1200) return; // слишком короткая запись — игнор

  state.busy = true;
  $("#send").disabled = true;
  $("#mic").disabled = true;
  const typing = addTyping();

  try {
    const wavB64 = await blobToWavBase64(blob);
    const res = await fetch("/api/voice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, audio: wavB64, mime: "audio/wav" }),
    });
    const data = await res.json();
    if (data.session_id) { state.sessionId = data.session_id; localStorage.setItem("verbo_sid", data.session_id); }
    typing.remove();
    if (data.transcript) addMessage("user", data.transcript);
    addMessage("bot", data.reply || I18N[state.lang].error);
    if (data.audio) playAudio(data.audio);
  } catch (e) {
    typing.remove();
    addMessage("bot", I18N[state.lang].error);
  } finally {
    state.busy = false;
    $("#send").disabled = false;
    $("#mic").disabled = false;
  }
}

// Декодируем запись (webm/mp4/opus) и перекодируем в WAV 16кГц моно — Gemini его точно принимает.
async function blobToWavBase64(blob) {
  const buf = await blob.arrayBuffer();
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC();
  const audio = await ctx.decodeAudioData(buf);
  ctx.close();
  return arrayBufferToBase64(encodeWav(audio, 16000));
}

function encodeWav(audioBuffer, targetRate) {
  let data = audioBuffer.getChannelData(0);
  if (audioBuffer.numberOfChannels > 1) {
    const d2 = audioBuffer.getChannelData(1);
    const mixed = new Float32Array(data.length);
    for (let i = 0; i < data.length; i++) mixed[i] = (data[i] + d2[i]) / 2;
    data = mixed;
  }
  const down = downsample(data, audioBuffer.sampleRate, targetRate);
  const out = new ArrayBuffer(44 + down.length * 2);
  const view = new DataView(out);
  const wr = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  wr(0, "RIFF"); view.setUint32(4, 36 + down.length * 2, true); wr(8, "WAVE"); wr(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true); view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); wr(36, "data");
  view.setUint32(40, down.length * 2, true);
  let off = 44;
  for (let i = 0; i < down.length; i++) {
    const s = Math.max(-1, Math.min(1, down[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    off += 2;
  }
  return out;
}

function downsample(data, srcRate, dstRate) {
  if (dstRate >= srcRate) return data;
  const ratio = srcRate / dstRate;
  const len = Math.floor(data.length / ratio);
  const out = new Float32Array(len);
  for (let i = 0; i < len; i++) out[i] = data[Math.floor(i * ratio)];
  return out;
}

function arrayBufferToBase64(buf) {
  let binary = "";
  const bytes = new Uint8Array(buf);
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function playAudio(b64) {
  try {
    const a = new Audio("data:audio/wav;base64," + b64);
    a.play().catch(() => {}); // если автоплей заблокирован — текст всё равно показан
  } catch (e) { /* ignore */ }
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
  $("#mic").addEventListener("click", toggleMic);
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
