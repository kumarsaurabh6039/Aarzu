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
const micBtn = document.getElementById("mic-btn");
const voiceToggleBtn = document.getElementById("voice-toggle");
const statusLine = document.getElementById("status-line");

// Voice CALL mode elements (hands-free, ChatGPT-style)
const voiceCallBtn = document.getElementById("voice-call-btn");
const voiceCallOverlay = document.getElementById("voice-call-overlay");
const voiceOrb = document.getElementById("voice-orb");
const voiceCallStatus = document.getElementById("voice-call-status");
const voiceCallTranscript = document.getElementById("voice-call-transcript");
const voiceCallEndBtn = document.getElementById("voice-call-end");
const voiceCallMuteBtn = document.getElementById("voice-call-mute");

// Fixed PIN required for owner (Saurabh) access. Anyone opening the app for
// the first time and claiming to be Saurabh must enter this correctly, or
// they're treated as a guest instead - so owner access is PIN-gated from
// the very first screen, not just assumed from a button tap.
//
// This same value is sent to the backend as the X-Aarzu-Owner-Key header
// on every request, and the backend only grants owner access if it
// matches OWNER_ACCESS_KEY in its own environment - so flipping a local
// flag in devtools can no longer fake owner access by itself.
const OWNER_PIN = "8521";

// ---- Mobile viewport height fix ------------------------------------------
function setAppHeight() {
  document.documentElement.style.setProperty("--app-height", `${window.innerHeight}px`);
}
setAppHeight();
window.addEventListener("resize", setAppHeight);
window.addEventListener("orientationchange", setAppHeight);

// ---- Local session state -------------------------------------------------
function loadState() {
  return {
    onboarded: localStorage.getItem("aarzu_onboarded") === "true",
    isOwner: localStorage.getItem("aarzu_is_owner") !== "false",
    visitorName: localStorage.getItem("aarzu_visitor_name") || null,
    history: JSON.parse(localStorage.getItem("aarzu_history") || "[]"),
    voiceOn: localStorage.getItem("aarzu_voice_on") === "true",
  };
}

let state = loadState();

function saveState() {
  localStorage.setItem("aarzu_onboarded", "true");
  localStorage.setItem("aarzu_is_owner", String(state.isOwner));
  if (state.visitorName) localStorage.setItem("aarzu_visitor_name", state.visitorName);
  else localStorage.removeItem("aarzu_visitor_name");
  localStorage.setItem("aarzu_history", JSON.stringify(state.history.slice(-20)));
  localStorage.setItem("aarzu_voice_on", String(state.voiceOn));
}

function updateSwitchButtonLabel() {
  switchUserBtn.textContent = state.isOwner ? "👋 New person?" : "🔙 Back to Saurabh";
}

function updateVoiceButton() {
  voiceToggleBtn.classList.toggle("active", state.voiceOn);
  voiceToggleBtn.setAttribute("aria-pressed", String(state.voiceOn));
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

// Rough script/language detector used only to pick a matching voice for
// text-to-speech and a matching recognition language for the mic.
function looksLikeHindi(text) {
  return /[\u0900-\u097F]/.test(text);
}

function addMessage(text, sender) {
  const row = document.createElement("div");
  row.className = `msg-row ${sender}`;

  if (sender === "aarzu" || sender === "typing") {
    const avatar = document.createElement("span");
    avatar.className = "msg-avatar";
    row.appendChild(avatar);
  }

  const bubble = document.createElement("div");
  bubble.className = `msg ${sender}`;
  bubble.textContent = text;
  row.appendChild(bubble);

  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return row;
}

function addTypingIndicator() {
  const row = document.createElement("div");
  row.className = "msg-row aarzu typing-row";
  row.innerHTML = `
    <span class="msg-avatar"></span>
    <div class="msg aarzu typing">
      <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
    </div>`;
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return row;
}

// ---- Text-to-speech helpers ------------------------------------------------
function pickVoice(lang) {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang === lang && /female|women/i.test(v.name)) ||
    voices.find((v) => v.lang === lang) ||
    null
  );
}

function makeUtterance(text) {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = looksLikeHindi(text) ? "hi-IN" : "en-US";
  utterance.rate = 1;
  utterance.pitch = 1.05;
  const voice = pickVoice(utterance.lang);
  if (voice) utterance.voice = voice;
  return utterance;
}

// Speaks a reply in normal chat mode - respects the header voice-reply toggle.
function speak(text) {
  if (!state.voiceOn) return;
  if (!("speechSynthesis" in window)) return;

  window.speechSynthesis.cancel();
  const utterance = makeUtterance(text);
  utterance.onstart = () => (statusLine.textContent = "speaking...");
  utterance.onend = () => (statusLine.textContent = "online");
  window.speechSynthesis.speak(utterance);
}

voiceToggleBtn.addEventListener("click", () => {
  state.voiceOn = !state.voiceOn;
  if (!state.voiceOn) window.speechSynthesis?.cancel();
  saveState();
  updateVoiceButton();
});

// ---- Shared "send a message to Aarzu" flow --------------------------------
// Used by both the normal text form AND hands-free voice call mode, so the
// two never drift out of sync (same history, same owner header, etc).
async function sendToAarzu(text, { fromVoiceCall = false } = {}) {
  text = (text || "").trim();
  if (!text) {
    if (fromVoiceCall) startCallListening();
    return;
  }

  addMessage(text, "user");

  if (!state.isOwner && !state.visitorName) {
    const detected = tryDetectName(text);
    if (detected) state.visitorName = detected;
  }

  const typingRow = fromVoiceCall ? null : addTypingIndicator();
  if (fromVoiceCall) setCallState("thinking", "Thinking...");

  let replyText;
  try {
    const headers = { "Content-Type": "application/json" };
    if (state.isOwner) headers["X-Aarzu-Owner-Key"] = OWNER_PIN;

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        message: text,
        is_owner: state.isOwner,
        visitor_name: state.visitorName,
        history: state.history,
      }),
    });
    const data = await res.json();
    replyText = data.response;
  } catch (err) {
    replyText =
      "Connection failed. Backend so raha hoga (Render free tier cold start) - try again in a few seconds.";
  }

  if (typingRow) typingRow.remove();
  addMessage(replyText, "aarzu");

  state.history.push({ role: "user", content: text });
  state.history.push({ role: "aarzu", content: replyText });
  saveState();

  if (fromVoiceCall) {
    speakForCall(replyText);
  } else {
    speak(replyText);
  }
}

// ---- Dictate-into-textbox mic (single utterance, doesn't auto-send) -------
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let listening = false;

if (SpeechRecognitionAPI) {
  recognizer = new SpeechRecognitionAPI();
  recognizer.continuous = false;
  recognizer.interimResults = true;

  recognizer.onstart = () => {
    listening = true;
    micBtn.classList.add("listening");
    statusLine.textContent = "listening...";
  };

  recognizer.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    input.value = transcript;
  };

  recognizer.onerror = () => {
    statusLine.textContent = "online";
  };

  recognizer.onend = () => {
    listening = false;
    micBtn.classList.remove("listening");
    statusLine.textContent = "online";
    if (input.value.trim()) {
      form.requestSubmit();
    }
  };
} else {
  micBtn.style.display = "none";
  if (voiceCallBtn) voiceCallBtn.style.display = "none";
}

micBtn.addEventListener("click", () => {
  if (!recognizer) return;

  if (listening) {
    recognizer.stop();
    return;
  }

  const lastText = state.history.length ? state.history[state.history.length - 1].content : "";
  recognizer.lang = looksLikeHindi(lastText) ? "hi-IN" : "en-IN";

  window.speechSynthesis?.cancel();
  try {
    recognizer.start();
  } catch (e) {
    // Already running / not allowed - ignore.
  }
});

// ---- Hands-free voice CALL mode (ChatGPT-style) ---------------------------
// Full-screen: listen -> think -> speak -> listen again, on a loop, until
// the person taps "end call". Tapping the orb while Aarzu is speaking
// interrupts her (barge-in) and starts listening immediately.

let callActive = false;
let callMuted = false;
let callRecognizer = null;
let callState = "idle"; // "listening" | "thinking" | "speaking"

function setCallState(next, statusText) {
  callState = next;
  voiceOrb.className = `voice-orb ${next}`;
  voiceCallStatus.textContent = statusText;
}

function buildCallRecognizer() {
  if (!SpeechRecognitionAPI) return null;

  const r = new SpeechRecognitionAPI();
  r.continuous = false;
  r.interimResults = true;

  const lastText = state.history.length ? state.history[state.history.length - 1].content : "";
  r.lang = looksLikeHindi(lastText) ? "hi-IN" : "en-IN";

  r.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    voiceCallTranscript.textContent = transcript;
  };

  r.onend = () => {
    if (!callActive) return;
    const text = voiceCallTranscript.textContent.trim();
    if (text) {
      sendToAarzu(text, { fromVoiceCall: true });
    } else if (!callMuted) {
      // Nothing heard yet (silence/timeout) - keep listening.
      startCallListening();
    }
  };

  r.onerror = (event) => {
    if (!callActive) return;
    if (event.error === "no-speech" || event.error === "aborted") {
      if (!callMuted) startCallListening();
    }
  };

  return r;
}

function startCallListening() {
  if (!callActive || callMuted) return;
  voiceCallTranscript.textContent = "";
  setCallState("listening", "Listening...");
  callRecognizer = buildCallRecognizer();
  if (!callRecognizer) return;
  try {
    callRecognizer.start();
  } catch (e) {
    // ignore duplicate-start errors
  }
}

function stopCallRecognition() {
  if (callRecognizer) {
    try {
      callRecognizer.stop();
    } catch (e) {
      // ignore
    }
    callRecognizer = null;
  }
}

// Always speaks (call mode ignores the header voice-toggle, since talking
// out loud is the entire point), and resumes listening once she's done.
function speakForCall(text) {
  if (!("speechSynthesis" in window)) {
    startCallListening();
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = makeUtterance(text);

  utterance.onstart = () => setCallState("speaking", "Speaking...");
  utterance.onend = () => {
    if (callActive) startCallListening();
  };
  utterance.onerror = () => {
    if (callActive) startCallListening();
  };

  window.speechSynthesis.speak(utterance);
}

function endCall() {
  callActive = false;
  callMuted = false;
  voiceCallMuteBtn.classList.remove("muted");
  stopCallRecognition();
  window.speechSynthesis?.cancel();
  voiceCallOverlay.classList.add("hidden");
}

if (voiceCallBtn) {
  voiceCallBtn.addEventListener("click", () => {
    if (!SpeechRecognitionAPI) {
      alert("Voice mode needs microphone speech recognition, which this browser doesn't support. Try Chrome.");
      return;
    }
    callActive = true;
    callMuted = false;
    voiceCallMuteBtn.classList.remove("muted");
    voiceCallOverlay.classList.remove("hidden");
    startCallListening();
  });
}

voiceCallEndBtn.addEventListener("click", endCall);

voiceCallMuteBtn.addEventListener("click", () => {
  callMuted = !callMuted;
  voiceCallMuteBtn.classList.toggle("muted", callMuted);

  if (callMuted) {
    stopCallRecognition();
    setCallState("listening", "Muted");
  } else {
    startCallListening();
  }
});

// Tap the orb to interrupt Aarzu while she's talking, and jump straight
// back to listening - just like barging into a real conversation.
voiceOrb.addEventListener("click", () => {
  if (!callActive) return;
  if (callState === "speaking") {
    window.speechSynthesis.cancel();
    startCallListening();
  }
});

// ---- One-time onboarding --------------------------------------------------
if (!state.onboarded) {
  onboardOverlay.classList.remove("hidden");
} else {
  state.history.forEach((turn) => {
    addMessage(turn.content, turn.role === "user" ? "user" : "aarzu");
  });
  updateSwitchButtonLabel();
  updateVoiceButton();
}

onboardYes.addEventListener("click", () => {
  const entered = prompt("Enter Saurabh's PIN:");
  if (entered !== null && entered.trim() === OWNER_PIN) {
    state = { ...state, onboarded: true, isOwner: true, visitorName: null, history: [] };
  } else {
    if (entered !== null) alert("Wrong PIN - continuing as a guest instead.");
    state = { ...state, onboarded: true, isOwner: false, visitorName: null, history: [] };
  }
  saveState();
  onboardOverlay.classList.add("hidden");
  updateSwitchButtonLabel();
});

onboardNo.addEventListener("click", () => {
  state = { ...state, onboarded: true, isOwner: false, visitorName: null, history: [] };
  saveState();
  onboardOverlay.classList.add("hidden");
  updateSwitchButtonLabel();
});

switchUserBtn.addEventListener("click", () => {
  if (state.isOwner) {
    const ok = confirm("Start a fresh chat for a new person on this device?");
    if (!ok) return;
    state = { ...state, isOwner: false, visitorName: null, history: [] };
  } else {
    const entered = prompt("Enter the PIN to switch back to Saurabh's chat:");
    if (entered === null) return;
    if (entered.trim() !== OWNER_PIN) {
      alert("Wrong PIN.");
      return;
    }
    state = { ...state, isOwner: true, visitorName: null, history: [] };
  }
  saveState();
  updateSwitchButtonLabel();
  messagesEl.innerHTML = "";
  addMessage("(Fresh chat started.)", "typing");
});

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendToAarzu(text);
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}
