/* ═══════════════════════════════════════════
   NexusAI Frontend — Production Script
   Supports local dev + GitHub Pages + Render
   ═══════════════════════════════════════════ */
'use strict';

/* ── API Configuration ──────────────────────────────────────
   Priority:
   1. window.NEXUSAI_API_URL  — explicit build-time override
   2. Localhost detection     — dev mode (localhost / 127.0.0.1)
   3. Production Render URL   — GitHub Pages / any other host
   ──────────────────────────────────────────────────────── */
const PROD_API_URL  = 'https://nexusai-1-pm2x.onrender.com';
const LOCAL_API_URL = 'http://localhost:5000';
const API_TIMEOUT_MS = 10000; // 10s — generous for Render cold-start

function resolveApiBase() {
  if (typeof window.NEXUSAI_API_URL === 'string' && window.NEXUSAI_API_URL.trim()) {
    return window.NEXUSAI_API_URL.trim();
  }
  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') {
    return LOCAL_API_URL;
  }
  return PROD_API_URL;
}

const API_BASE = resolveApiBase();

/* ── Fetch wrapper: timeout + abort ─────────────────────── */
async function apiFetch(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, signal: controller.signal });
    clearTimeout(timer);
    return res;
  } catch (err) {
    clearTimeout(timer);
    throw Object.assign(err, { isTimeout: err.name === 'AbortError' });
  }
}

/* ── Suggestion Cards ── */
const SUGGESTIONS = [
  { icon: '🤖', text: 'What is Artificial Intelligence?' },
  { icon: '🧠', text: 'Explain deep learning' },
  { icon: '☁️', text: 'What is cloud computing?' },
  { icon: '🐍', text: 'What is Python?' },
  { icon: '🔒', text: 'What is cybersecurity?' },
  { icon: '🔀', text: 'What is Git?' },
  { icon: '📦', text: 'What is Docker?' },
  { icon: '⚡', text: 'What is a REST API?' },
  { icon: '🗄️', text: 'What is SQL?' },
  { icon: '🚀', text: 'What is DevOps?' },
  { icon: '📊', text: 'What is machine learning?' },
  { icon: '🌐', text: 'What is HTML?' },
];

/* ── DOM References ── */
const messagesContainer = document.getElementById('messagesContainer');
const chatInput          = document.getElementById('chatInput');
const sendBtn            = document.getElementById('sendBtn');
const topicList          = document.getElementById('topicList');
const statusIndicator    = document.getElementById('statusDot');
const suggestionGrid     = document.getElementById('suggestionGrid');
const themeToggle        = document.getElementById('themeToggle');
const sidebarToggle      = document.getElementById('sidebarToggle');
const sidebar            = document.getElementById('sidebar');
const newChatBtn         = document.getElementById('newChatBtn');
const voiceBtn           = document.getElementById('voiceBtn');
const voiceBtnInline     = document.getElementById('voiceBtnInline');
const toast              = document.getElementById('toast');

/* ── State ── */
let isLoading = false;
let recognition = null;
let currentUtterance = null;
let typingCounter = 0;
let toastTimer = null;

/* ═══════════════════════════════
   INIT
   ═══════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  setupTheme();
  buildSuggestions();
  loadTopics();
  checkHealth();
  setupAutoResize();
  setupKeyboard();
  setupSidebar();
  setupVoice();
  // Periodic health check every 30s
  setInterval(checkHealth, 30000);
});

/* ═══════════════════════════════
   SUGGESTIONS
   ═══════════════════════════════ */
function buildSuggestions() {
  const grid = document.getElementById('suggestionGrid');
  if (!grid) return;
  grid.innerHTML = '';
  SUGGESTIONS.forEach(s => {
    const card = document.createElement('div');
    card.className = 'suggestion-card';
    card.innerHTML = `<span class="card-icon">${s.icon}</span><span class="card-text">${escapeHtml(s.text)}</span>`;
    card.addEventListener('click', () => sendMessage(s.text));
    grid.appendChild(card);
  });
}

/* ═══════════════════════════════
   TOPICS
   ═══════════════════════════════ */
async function loadTopics() {
  try {
    const res = await apiFetch('/topics');
    if (!res.ok) throw new Error('Failed to load topics');
    const data = await res.json();

    topicList.innerHTML = '';

    if (!data.topics || data.topics.length === 0) {
      topicList.innerHTML = '<p style="font-size:12px;color:var(--text3);padding:6px;">No topics available</p>';
      return;
    }

    data.topics.forEach(t => {
      const el = document.createElement('div');
      el.className = 'topic-item';
      el.innerHTML = `
        <div class="topic-name">
          <div class="topic-dot"></div>
          <span class="topic-label">${escapeHtml(t.name)}</span>
        </div>
        <span class="topic-count">${t.count}</span>
      `;
      el.addEventListener('click', () => {
        document.querySelectorAll('.topic-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');
        sendMessage(`Tell me about ${t.name}`);
      });
      topicList.appendChild(el);
    });
  } catch (_) {
    topicList.innerHTML = '<p style="font-size:12px;color:var(--text3);padding:6px;">Could not load topics</p>';
  }
}

/* ═══════════════════════════════
   HEALTH CHECK
   ═══════════════════════════════ */
async function checkHealth() {
  try {
    const res = await apiFetch('/health');
    if (res.ok) {
      setStatus('online', 'Online');
    } else {
      setStatus('offline', 'Offline');
    }
  } catch (_) {
    setStatus('offline', 'Offline');
  }
}

function setStatus(state, label) {
  statusIndicator.className = `status-indicator ${state}`;
  const text = statusIndicator.querySelector('.status-text');
  if (text) text.textContent = label;
}

/* ═══════════════════════════════
   INPUT
   ═══════════════════════════════ */
function setupAutoResize() {
  chatInput.addEventListener('input', autoResizeTextarea);
}

function autoResizeTextarea() {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
}

function setupKeyboard() {
  chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });
  sendBtn.addEventListener('click', handleSend);
}

function handleSend() {
  const text = chatInput.value.trim();
  if (!text || isLoading) return;
  sendMessage(text);
}

/* ═══════════════════════════════
   SEND MESSAGE
   ═══════════════════════════════ */
async function sendMessage(text) {
  if (!text || isLoading) return;

  // Remove welcome screen
  const welcome = document.getElementById('welcomeScreen');
  if (welcome) welcome.remove();

  appendUserMessage(text);
  chatInput.value = '';
  chatInput.style.height = 'auto';

  const typingId = appendTypingIndicator();
  isLoading = true;
  sendBtn.disabled = true;

  try {
    const res = await apiFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();
    removeTypingIndicator(typingId);
    appendBotMessage(data);

  } catch (err) {
    removeTypingIndicator(typingId);
    const isTimeout = err.isTimeout;
    const msg = isTimeout
      ? '⏱️ The server took too long to respond. The Render backend may be waking up from sleep — please wait 20 seconds and try again.'
      : '⚠️ Could not connect to the NexusAI server.\n\n• Local dev: make sure `python backend/app.py` is running on port 5000.\n• Production: the Render service may be starting up — wait ~20 s and retry.';
    appendBotMessage({
      answer: msg,
      topic: isTimeout ? 'Timeout' : 'Connection Error',
      confidence: 0,
      source: 'error',
    });
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

/* ═══════════════════════════════
   RENDER MESSAGES
   ═══════════════════════════════ */
function appendUserMessage(text) {
  const wrap = document.createElement('div');
  wrap.className = 'message';
  wrap.innerHTML = `
    <div class="message-row user">
      <div class="avatar">👤</div>
      <div class="bubble">
        <div class="bubble-text">${escapeHtml(text)}</div>
      </div>
    </div>`;
  messagesContainer.appendChild(wrap);
  scrollToBottom();
}

function appendBotMessage(data) {
  const wrap = document.createElement('div');
  wrap.className = 'message';

  // Build bubble HTML structure
  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  // Meta row
  const meta = buildMetaRow(data);
  bubble.appendChild(meta);

  // Answer text (will be typed in)
  const bubbleText = document.createElement('div');
  bubbleText.className = 'bubble-text';
  bubble.appendChild(bubbleText);

  // Alternatives
  if (data.alternatives && data.alternatives.length > 0) {
    bubble.appendChild(buildAlternatives(data.alternatives, 'Related questions'));
  }

  // Suggestions (no-match fallback)
  if (data.suggestions && data.suggestions.length > 0) {
    bubble.appendChild(buildAlternatives(data.suggestions, 'Maybe you meant'));
  }

  // Action buttons
  bubble.appendChild(buildActionButtons(data.answer));

  const row = document.createElement('div');
  row.className = 'message-row bot';

  const avatar = document.createElement('div');
  avatar.className = 'avatar bot-avatar';
  avatar.innerHTML = `<svg width="14" height="14" viewBox="0 0 28 28" fill="none"><polygon points="14,2 26,8 26,20 14,26 2,20 2,8" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="14" cy="14" r="3" fill="currentColor"/></svg>`;

  row.appendChild(avatar);
  row.appendChild(bubble);
  wrap.appendChild(row);
  messagesContainer.appendChild(wrap);
  scrollToBottom();

  // Typing animation
  typeText(bubbleText, data.answer, () => scrollToBottom());
}

function buildMetaRow(data) {
  const meta = document.createElement('div');
  meta.className = 'bot-meta';

  const badge = document.createElement('span');
  badge.className = `topic-badge${data.source === 'ai_generated' ? ' ai' : ''}`;
  badge.textContent = data.topic || 'General';
  meta.appendChild(badge);

  if (data.confidence > 0) {
    const pct = Math.min(data.confidence, 99);
    const confWrap = document.createElement('div');
    confWrap.className = 'confidence-bar-wrap';
    confWrap.innerHTML = `
      <div class="confidence-bar">
        <div class="confidence-fill" style="width:${pct}%"></div>
      </div>
      <span>${pct}%</span>`;
    meta.appendChild(confWrap);
  }

  if (data.source === 'ai_generated') {
    const aiTag = document.createElement('span');
    aiTag.style.cssText = 'font-size:10px;color:#c084fc;font-weight:500;font-family:var(--font-mono);';
    aiTag.textContent = '✦ AI';
    meta.appendChild(aiTag);
  }

  return meta;
}

function buildAlternatives(items, label) {
  const div = document.createElement('div');
  div.className = 'alternatives';
  div.innerHTML = `<div class="alternatives-label">${label}</div>`;
  items.forEach(item => {
    const el = document.createElement('div');
    el.className = 'alt-item';
    el.innerHTML = `<span class="alt-arrow">›</span> ${escapeHtml(item.question)}`;
    el.addEventListener('click', () => sendMessage(item.question));
    div.appendChild(el);
  });
  return div;
}

function buildActionButtons(answerText) {
  const actions = document.createElement('div');
  actions.className = 'bubble-actions';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'bubble-action-btn';
  copyBtn.innerHTML = '📋 Copy';
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(answerText);
      copyBtn.innerHTML = '✓ Copied';
      setTimeout(() => { copyBtn.innerHTML = '📋 Copy'; }, 2000);
    } catch (_) {
      showToast('Copy failed — try manually selecting the text');
    }
  });

  const ttsBtn = document.createElement('button');
  ttsBtn.className = 'bubble-action-btn tts-btn';
  ttsBtn.innerHTML = '🔊 Listen';
  ttsBtn.addEventListener('click', () => speakText(answerText, ttsBtn));

  actions.appendChild(copyBtn);
  actions.appendChild(ttsBtn);
  return actions;
}

/* ═══════════════════════════════
   TYPING ANIMATION
   ═══════════════════════════════ */
function typeText(el, text, onDone, speed = 9) {
  let i = 0;
  el.textContent = '';
  const interval = setInterval(() => {
    if (i < text.length) {
      el.textContent += text[i++];
      if (i % 25 === 0) scrollToBottom();
    } else {
      clearInterval(interval);
      if (onDone) onDone();
    }
  }, speed);
}

/* ═══════════════════════════════
   TYPING INDICATOR
   ═══════════════════════════════ */
function appendTypingIndicator() {
  const id = `typing-${++typingCounter}`;
  const wrap = document.createElement('div');
  wrap.className = 'message';
  wrap.id = id;
  wrap.innerHTML = `
    <div class="message-row bot">
      <div class="avatar bot-avatar">
        <svg width="14" height="14" viewBox="0 0 28 28" fill="none">
          <polygon points="14,2 26,8 26,20 14,26 2,20 2,8" fill="none" stroke="currentColor" stroke-width="2"/>
          <circle cx="14" cy="14" r="3" fill="currentColor"/>
        </svg>
      </div>
      <div class="bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>`;
  messagesContainer.appendChild(wrap);
  scrollToBottom();
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* ═══════════════════════════════
   SCROLL
   ═══════════════════════════════ */
function scrollToBottom() {
  messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
}

/* ═══════════════════════════════
   TEXT-TO-SPEECH
   ═══════════════════════════════ */
function speakText(text, btn) {
  const synth = window.speechSynthesis;
  if (!synth) { showToast('Text-to-speech not supported in this browser'); return; }

  if (currentUtterance) {
    synth.cancel();
    currentUtterance = null;
    if (btn) { btn.classList.remove('speaking'); btn.innerHTML = '🔊 Listen'; }
    return;
  }

  const utter = new SpeechSynthesisUtterance(text.slice(0, 600));
  utter.rate = 0.95;
  utter.pitch = 1;

  const reset = () => {
    currentUtterance = null;
    if (btn) { btn.classList.remove('speaking'); btn.innerHTML = '🔊 Listen'; }
  };

  utter.onend = reset;
  utter.onerror = reset;
  currentUtterance = utter;

  if (btn) { btn.classList.add('speaking'); btn.innerHTML = '⏹ Stop'; }
  synth.speak(utter);
}

/* ═══════════════════════════════
   VOICE INPUT
   ═══════════════════════════════ */
function setupVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    [voiceBtn, voiceBtnInline].forEach(b => {
      if (b) { b.title = 'Voice input not supported in this browser'; b.style.opacity = '0.35'; b.style.cursor = 'not-allowed'; }
    });
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  let voiceOverlay = null;

  function startVoice() {
    try {
      recognition.start();
    } catch (_) { return; }

    voiceOverlay = document.createElement('div');
    voiceOverlay.className = 'voice-overlay';
    voiceOverlay.innerHTML = `
      <div class="voice-modal">
        <div class="voice-circle">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          </svg>
        </div>
        <p class="voice-text">Listening…</p>
        <button class="voice-stop-btn">Stop Recording</button>
      </div>`;

    voiceOverlay.querySelector('.voice-stop-btn').addEventListener('click', stopVoice);
    voiceOverlay.addEventListener('click', e => { if (e.target === voiceOverlay) stopVoice(); });
    document.body.appendChild(voiceOverlay);

    [voiceBtn, voiceBtnInline].forEach(b => { if (b) b.classList.add('recording'); });
  }

  function stopVoice() {
    recognition.stop();
    if (voiceOverlay) { voiceOverlay.remove(); voiceOverlay = null; }
    [voiceBtn, voiceBtnInline].forEach(b => { if (b) b.classList.remove('recording'); });
  }

  recognition.onresult = e => {
    let transcript = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript;
    }
    chatInput.value = transcript;
    autoResizeTextarea();

    if (e.results[e.resultIndex].isFinal) {
      stopVoice();
      setTimeout(() => handleSend(), 300);
    }
  };

  recognition.onend = stopVoice;
  recognition.onerror = () => {
    stopVoice();
    showToast('Voice recognition error — please try again');
  };

  [voiceBtn, voiceBtnInline].forEach(b => {
    if (b) b.addEventListener('click', startVoice);
  });
}

/* ═══════════════════════════════
   THEME
   ═══════════════════════════════ */
function setupTheme() {
  let saved = 'dark';
  try { saved = localStorage.getItem('nexusai-theme') || 'dark'; } catch (_) {}
  applyTheme(saved);
  themeToggle.checked = saved === 'dark';

  themeToggle.addEventListener('change', () => {
    const t = themeToggle.checked ? 'dark' : 'light';
    applyTheme(t);
    try { localStorage.setItem('nexusai-theme', t); } catch (_) {}
  });
}

function applyTheme(theme) {
  document.body.className = theme;
}

/* ═══════════════════════════════
   SIDEBAR
   ═══════════════════════════════ */
function setupSidebar() {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
  });

  newChatBtn.addEventListener('click', () => {
    // Clear messages
    messagesContainer.innerHTML = '';

    // Re-insert welcome screen
    const ws = document.createElement('div');
    ws.id = 'welcomeScreen';
    ws.className = 'welcome-screen';
    ws.innerHTML = `
      <div class="welcome-badge">AI · FAQ · 500+ Answers</div>
      <div class="welcome-icon">
        <svg width="48" height="48" viewBox="0 0 28 28" fill="none">
          <polygon points="14,2 26,8 26,20 14,26 2,20 2,8" fill="none" stroke="currentColor" stroke-width="1.5"/>
          <polygon points="14,7 21,11 21,17 14,21 7,17 7,11" fill="currentColor" opacity="0.25"/>
          <circle cx="14" cy="14" r="3.5" fill="currentColor"/>
        </svg>
      </div>
      <h1 class="welcome-title">Hello, I'm <span class="gradient-text">NexusAI</span></h1>
      <p class="welcome-sub">Your intelligent technical FAQ assistant. Ask me anything about AI, coding, cloud, DevOps, and more.</p>
      <div class="suggestion-grid" id="suggestionGrid"></div>
    `;
    messagesContainer.appendChild(ws);
    buildSuggestions();

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    chatInput.focus();

    // Deselect topics
    document.querySelectorAll('.topic-item').forEach(i => i.classList.remove('active'));

    // Stop any TTS
    if (currentUtterance) {
      window.speechSynthesis?.cancel();
      currentUtterance = null;
    }
  });
}

/* ═══════════════════════════════
   TOAST
   ═══════════════════════════════ */
function showToast(msg, duration = 3000) {
  if (toastTimer) clearTimeout(toastTimer);
  toast.textContent = msg;
  toast.classList.add('show');
  toastTimer = setTimeout(() => {
    toast.classList.remove('show');
    toastTimer = null;
  }, duration);
}

/* ═══════════════════════════════
   UTILITY
   ═══════════════════════════════ */
function escapeHtml(str) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, c => map[c]);
}