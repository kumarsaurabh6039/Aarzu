// ⚠️ After deploying the backend on Render, replace this with your real URL.
// Example: https://aarzu-api.onrender.com
const API_BASE = "http://127.0.0.1:8000";

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");

function addMessage(text, sender) {
  const el = document.createElement("div");
  el.className = `msg ${sender}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  const typingEl = addMessage("Aarzu is typing...", "aarzu typing");

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    typingEl.remove();
    addMessage(data.response, "aarzu");
  } catch (err) {
    typingEl.remove();
    addMessage("Connection failed. Backend so-raha hoga (Render free tier cold start) — try again in a few seconds.", "aarzu");
  }
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => { });
  });
}
