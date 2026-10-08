const STORAGE_KEY = "smart-cs-sessions";

function getSessions() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(value) ? value.filter(item => item && typeof item.id === "string") : [];
  } catch {
    return [];
  }
}

function saveSession(id, title) {
  const existing = getSessions();
  const sessions = existing.filter(item => item.id !== id);
  const previous = existing.find(item => item.id === id);
  sessions.unshift({ id, title: previous?.title || title, updatedAt: new Date().toISOString() });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, 100)));
  renderRecent();
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function renderRecent() {
  const container = document.getElementById("recent-sessions");
  if (!container) return;
  container.replaceChildren();
  const sessions = getSessions().slice(0, 5);
  if (!sessions.length) {
    const empty = document.createElement("div");
    empty.className = "recent-empty";
    empty.textContent = "还没有对话记录";
    container.append(empty);
    return;
  }
  for (const session of sessions) {
    const link = document.createElement("a");
    link.className = "recent-link";
    link.href = "/?session=" + encodeURIComponent(session.id);
    link.textContent = "◌  " + session.title;
    container.append(link);
  }
}

function addMessage(container, role, content, timestamp) {
  const item = document.createElement("div");
  item.className = "message " + (role === "user" ? "user" : "assistant");
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "我" : "✦";
  const body = document.createElement("div");
  body.className = "message-body";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? (timestamp ? formatDate(timestamp) : "") : "FinServe Agent" + (timestamp ? " · " + formatDate(timestamp) : "");
  if (!meta.textContent) meta.hidden = true;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;
  body.append(meta, bubble);
  item.append(avatar, body);
  container.append(item);
  container.scrollTop = container.scrollHeight;
  return item;
}

async function fetchHistory(id) {
  const response = await fetch("/api/history/" + encodeURIComponent(id));
  if (!response.ok) throw new Error("无法读取对话记录，请稍后重试。");
  return (await response.json()).messages || [];
}

function initChat() {
  const messages = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const send = document.getElementById("send-button");
  const newChat = document.getElementById("new-chat");
  const error = document.getElementById("chat-error");
  let sessionId = new URLSearchParams(location.search).get("session");
  let busy = false;
  let loading = Boolean(sessionId);

  newChat.addEventListener("click", () => {
    sessionId = null;
    loading = false;
    send.disabled = false;
    history.replaceState(null, "", "/");
    messages.replaceChildren(document.getElementById("welcome") || createWelcome());
    error.hidden = true;
    input.focus();
  });

  function createWelcome() {
    const welcome = document.createElement("div");
    welcome.className = "welcome";
    welcome.id = "welcome";
    welcome.innerHTML = '<div class="welcome-symbol">✦</div><div class="eyebrow">新的对话</div><h2>你好，有什么可以帮你？</h2><p>输入问题即可开始。</p>';
    return welcome;
  }

  if (sessionId) {
    const requestedSessionId = sessionId;
    send.disabled = true;
    fetchHistory(sessionId).then(items => {
      if (sessionId !== requestedSessionId) return;
      messages.replaceChildren();
      if (!items.length) messages.append(createWelcome());
      items.forEach(item => addMessage(messages, item.role, item.content, item.timestamp));
    }).catch(err => {
      if (sessionId !== requestedSessionId) return;
      error.textContent = err.message;
      error.hidden = false;
    }).finally(() => {
      if (sessionId !== requestedSessionId) return;
      loading = false;
      send.disabled = false;
    });
  }

  document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    input.focus();
  }));
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || busy || loading) return;
    busy = true;
    send.disabled = true;
    newChat.disabled = true;
    error.hidden = true;
    document.getElementById("welcome")?.remove();
    const pending = addMessage(messages, "user", message);
    input.value = "";
    const waiting = addMessage(messages, "assistant", "正在整理回答…");
    try {
      const response = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      if (!response.ok) throw new Error(response.status === 422 ? "请输入有效的问题（最多 4000 字）。" : "发送失败，请稍后重试。");
      const data = await response.json();
      sessionId = data.session_id;
      history.replaceState(null, "", "/?session=" + encodeURIComponent(sessionId));
      saveSession(sessionId, message.slice(0, 28));
      waiting.querySelector(".bubble").textContent = data.response;
    } catch (err) {
      pending.remove();
      waiting.remove();
      input.value = message;
      error.textContent = err.message;
      error.hidden = false;
      if (!messages.children.length) messages.append(createWelcome());
    } finally {
      busy = false;
      send.disabled = false;
      newChat.disabled = false;
      input.focus();
    }
  });
}

function initHistory() {
  const list = document.getElementById("history-list");
  const detail = document.getElementById("history-detail");
  const search = document.getElementById("history-search");
  const count = document.getElementById("session-count");
  let selected = null;

  async function selectSession(session) {
    selected = session.id;
    renderList();
    detail.replaceChildren();
    const loading = document.createElement("div");
    loading.className = "list-empty";
    loading.textContent = "正在加载对话…";
    detail.append(loading);
    try {
      const items = await fetchHistory(session.id);
      if (selected !== session.id) return;
      detail.replaceChildren();
      const header = document.createElement("div");
      header.className = "detail-header";
      const heading = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = session.title;
      const date = document.createElement("small");
      date.textContent = "最近更新 · " + formatDate(session.updatedAt);
      heading.append(title, date);
      const link = document.createElement("a");
      link.href = "/?session=" + encodeURIComponent(session.id);
      link.textContent = "继续对话 →";
      header.append(heading, link);
      const messages = document.createElement("div");
      messages.className = "detail-messages";
      if (items.length) items.forEach(item => addMessage(messages, item.role, item.content, item.timestamp));
      else {
        const empty = document.createElement("div");
        empty.className = "list-empty";
        empty.textContent = "这条对话已过期，暂无可显示的消息。";
        messages.append(empty);
      }
      detail.append(header, messages);
    } catch (err) {
      loading.textContent = err.message;
    }
  }

  function renderList() {
    const sessions = getSessions();
    count.textContent = sessions.length;
    list.replaceChildren();
    const query = search.value.trim().toLowerCase();
    const filtered = sessions.filter(session => session.title.toLowerCase().includes(query));
    if (!filtered.length) {
      const empty = document.createElement("div");
      empty.className = "list-empty";
      empty.textContent = sessions.length ? "没有找到匹配的对话。" : "还没有对话记录。先去开始一次咨询吧。";
      list.append(empty);
      return;
    }
    for (const session of filtered) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "history-item" + (selected === session.id ? " active" : "");
      const title = document.createElement("div");
      title.className = "history-item-title";
      title.textContent = session.title;
      const preview = document.createElement("div");
      preview.className = "history-item-preview";
      preview.textContent = "点击查看完整对话";
      const date = document.createElement("div");
      date.className = "history-item-date";
      date.textContent = formatDate(session.updatedAt);
      button.append(title, preview, date);
      button.addEventListener("click", () => selectSession(session));
      list.append(button);
    }
  }
  search.addEventListener("input", renderList);
  renderList();
  if (getSessions().length) selectSession(getSessions()[0]);
}

renderRecent();
if (document.body.dataset.page === "chat") initChat();
if (document.body.dataset.page === "history") initHistory();
