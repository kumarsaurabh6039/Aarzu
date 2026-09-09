// After deploying the backend on Render, replace this with your real URL.
// Example: https://aarzu-api.onrender.com
const API_BASE = "https://aarzu-api.onrender.com";
const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const switchUserBtn = document.getElementById("switch-user");
const onboardOverlay = document.getElementById("onboard-overlay");
const onboardYes = document.getElementById("onboard-yes");
const onboardNo = document.getElementById("onboard-no");

// ---- Mobile viewport height fix ------------------------------------------
// 100vh on phones includes space hidden behind the browser's address bar,
// which was cutting off the message list / input box. dvh (in style.css)
// fixes this on modern browsers; this JS is a fallback for older ones.
function setAppHeight() {
  document.documentElement.style.setProperty("--app-height", `${window.innerHeight}px`);
}
setAppHeight();
window.addEventListener("resize", setAppHeight);
window.addEventListener("orientationchange", setAppHeight);

// ---- Local session state -------------------------------------------------
// No login system by design (personal, single-owner app). The very first
// time the app is opened on a device, we ask once whether it's Saurabh's
// device - after that we just remember, instead of asking every time.

function loadState() {
  return {
    onboarded: localStorage.getItem("aarzu_onboarded") === "true",
    isOwner: localStorage.getItem("aarzu_is_owner") !== "false",
    visitorName: localStorage.getItem("aarzu_visitor_name") || null,
    history: JSON.parse(localStorage.getItem("aarzu_history") || "[]"),
  };
}

let state = loadState();

function saveState() {
  localStorage.setItem("aarzu_onboarded", "true");
  localStorage.setItem("aarzu_is_owner", String(state.isOwner));
  if (state.visitorName) localStorage.setItem("aarzu_visitor_name", state.visitorName);
  else localStorage.removeItem("aarzu_visitor_name");
  localStorage.setItem("aarzu_history", JSON.stringify(state.history.slice(-20)));
}

function updateSwitchButtonLabel() {
  switchUserBtn.textContent = state.isOwner ? "👋 New person?" : "🔙 Back to Saurabh";
}

// Very light heuristic to catch "I'm X" / "mera naam X hai" style intros,
// so Aarzu doesn't keep asking once someone has already told her their name.
function tryDetectName(text) {
  const patterns = [
    /\bmy name is ([a-zA-Z]{2,20})\b/i,
    /\bi'?m ([a-zA-Z]{2,20})\b/i,
    /\bmera naam ([a-zA-Z]{2,20}) hai\b/i,
    /\bmain ([a-zA-Z]{2,20}) (hoon|hu)\b/i,
  ];
  for (const p of patterns) {
    const match = text.match(p);
    if (match) return match[1];
  }
  return null;
}

function addMessage(text, sender) {
  const el = document.createElement("div");
  el.className = `msg ${sender}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

// ---- One-time onboarding --------------------------------------------------
if (!state.onboarded) {
  onboardOverlay.classList.remove("hidden");
} else {
  state.history.forEach((turn) => {
    addMessage(turn.content, turn.role === "user" ? "user" : "aarzu");
  });
  updateSwitchButtonLabel();
}

onboardYes.addEventListener("click", () => {
  state = { onboarded: true, isOwner: true, visitorName: null, history: [] };
  saveState();
  onboardOverlay.classList.add("hidden");
  updateSwitchButtonLabel();
});

onboardNo.addEventListener("click", () => {
  state = { onboarded: true, isOwner: false, visitorName: null, history: [] };
  saveState();
  onboardOverlay.classList.add("hidden");
  updateSwitchButtonLabel();
});

switchUserBtn.addEventListener("click", () => {
  if (state.isOwner) {
    const ok = confirm("Start a fresh chat for a new person on this device?");
    if (!ok) return;
    state = { onboarded: true, isOwner: false, visitorName: null, history: [] };
  } else {
    const ok = confirm("Switch back to Saurabh's chat?");
    if (!ok) return;
    state = { onboarded: true, isOwner: true, visitorName: null, history: [] };
  }
  saveState();
  updateSwitchButtonLabel();
  messagesEl.innerHTML = "";
  addMessage("(Fresh chat started.)", "typing");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  if (!state.isOwner && !state.visitorName) {
    const detected = tryDetectName(text);
    if (detected) state.visitorName = detected;
  }

  const typingEl = addMessage("Aarzu is typing...", "aarzu typing");

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        is_owner: state.isOwner,
        visitor_name: state.visitorName,
        history: state.history,
      }),
    });
    const data = await res.json();
    typingEl.remove();
    addMessage(data.response, "aarzu");

    state.history.push({ role: "user", content: text });
    state.history.push({ role: "aarzu", content: data.response });
    saveState();
  } catch (err) {
    typingEl.remove();
    addMessage("Connection failed. Backend so raha hoga (Render free tier cold start) - try again in a few seconds.", "aarzu");
  }
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => { });
  });
}
