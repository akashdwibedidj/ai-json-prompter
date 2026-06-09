/* ── script.js — Pipeline Runner frontend logic ── */

"use strict";

// ── Provider presets (mirrors server.py) ──────────────────────────────────────
const PRESETS = {
  ollama:      { base_url: "http://localhost:11434/v1", model: "mistral" },
  openai:      { base_url: "https://api.openai.com/v1", model: "gpt-4o" },
  gemini:      { base_url: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-1.5-pro" },
  claude:      { base_url: "https://api.anthropic.com/v1", model: "claude-sonnet-4-6" },
  openrouter:  { base_url: "https://openrouter.ai/api/v1", model: "mistralai/mistral-7b-instruct" },
};

// ── State ──────────────────────────────────────────────────────────────────────
let running       = false;
let jsonOpen      = false;
let jsonData      = null;
let elapsedTimer  = null;
let startTime     = null;
let apiKeyVisible = false;

// ── DOM references ─────────────────────────────────────────────────────────────
const $  = id => document.getElementById(id);
const ta          = $("user-textarea");
const runBtn      = $("run-btn");
const runBtnLabel = $("run-btn-label");
const termScroll  = $("terminal-scroll");
const chatScroll  = $("chat-scroll");
const spinner     = $("spinner");
const statusText  = $("status-text");
const elapsedEl   = $("elapsed");
const stageEl     = $("stage-indicator");
const jsonZone    = $("json-zone");
const jsonBody    = $("json-body");
const jsonPre     = $("json-pre");
const jsonChevron = $("json-chevron");
const jsonHeader  = $("json-header");
const jsonSize    = $("json-size");
const connError   = $("conn-error");
const connErrMsg  = $("conn-error-msg");
const emptyState  = $("empty-state");
const providerBadge = $("topbar-provider");

// Settings modal
const overlay       = $("settings-overlay");
const modal         = $("settings-modal");
const providerSel   = $("provider-select");
const modelInput    = $("model-input");
const baseUrlInput  = $("base-url-input");
const apikeyInput   = $("apikey-input");
const saveStatus    = $("save-status");

// ── Terminal line classifier ───────────────────────────────────────────────────
function classifyLine(line) {
  const t = line.trim();
  if (!t) return "c-dim";
  if (t.startsWith("---"))                               return "c-stage";
  if (t.startsWith("📊") || t.includes("Token Usage"))  return "c-metric";
  if (t.includes("PIPELINE SUCCESS") || t.startsWith("================")) return "c-success";
  if (t.startsWith("  ✅") || (t.startsWith("✅") && !t.includes("PIPELINE"))) return "c-ok";
  if (t.startsWith("✅"))                               return "c-ok";
  if (t.startsWith("  ⚠") || t.startsWith("⚠"))        return "c-warn";
  if (t.startsWith("❌") || t.startsWith("  ❌"))       return "c-err";
  if (t.startsWith("[ERROR]"))                           return "c-err";
  if (t.match(/^(Extracted|Generated|Validated|Saved)/)) return "c-info";
  if (t.startsWith("Issue:") || t.startsWith("To run") || t.startsWith("cd ")) return "c-key";
  if (t.match(/^\d+\./))                                 return "c-dim";
  if (t.startsWith("Attempt"))                           return "c-dim";
  if (t.startsWith("[DEV MODE]"))                        return "c-warn";
  return "c-default";
}

// ── Detect current stage from line text ───────────────────────────────────────
function detectStage(line) {
  const m = line.match(/---\s*(STAGE \d+[^-]*?)---/);
  if (m) stageEl.textContent = m[1].trim();
  if (line.includes("CODEGEN"))   stageEl.textContent = "CODEGEN";
  if (line.includes("PIPELINE SUCCESS")) stageEl.textContent = "";
}

// ── Append one line to terminal ────────────────────────────────────────────────
function appendLine(text) {
  detectStage(text);
  const span = document.createElement("span");
  span.className = "tl " + classifyLine(text);
  span.textContent = text + "\n";
  const cursor = $("cursor");
  if (cursor) termScroll.insertBefore(span, cursor);
  else        termScroll.appendChild(span);
  termScroll.scrollTop = termScroll.scrollHeight;
}

// ── Chat bubbles ───────────────────────────────────────────────────────────────
function addBubble(text, type = "bubble-sys") {
  const d = document.createElement("div");
  d.className = "bubble " + type;
  d.textContent = text;
  chatScroll.appendChild(d);
  chatScroll.scrollTop = chatScroll.scrollHeight;
}

// ── Status helpers ─────────────────────────────────────────────────────────────
function setStatus(state) {
  spinner.className   = state;           // idle | running | done | error
  const labels = { idle: "idle", running: "running…", done: "done", error: "error" };
  statusText.textContent = labels[state] || state;
}

function startElapsed() {
  startTime = Date.now();
  elapsedEl.textContent = "0.0s";
  elapsedTimer = setInterval(() => {
    elapsedEl.textContent = ((Date.now() - startTime) / 1000).toFixed(1) + "s";
  }, 100);
}

function stopElapsed() {
  clearInterval(elapsedTimer);
  elapsedEl.textContent = ((Date.now() - startTime) / 1000).toFixed(1) + "s";
}

// ── JSON panel ─────────────────────────────────────────────────────────────────
function toggleJson() {
  jsonOpen = !jsonOpen;
  jsonBody.classList.toggle("open", jsonOpen);
  jsonChevron.classList.toggle("open", jsonOpen);
  jsonHeader.setAttribute("aria-expanded", jsonOpen);
}

async function fetchAndShowJson() {
  try {
    const res = await fetch("/output-json");
    if (!res.ok) return;
    jsonData = await res.json();
    const text = JSON.stringify(jsonData, null, 2);
    jsonPre.textContent = text;
    jsonSize.textContent = `${(text.length / 1024).toFixed(1)} KB`;
    jsonZone.removeAttribute("hidden");
    if (!jsonOpen) toggleJson();
  } catch (_) {}
}

function downloadJson() {
  if (!jsonData) return;
  const blob = new Blob([JSON.stringify(jsonData, null, 2)], { type: "application/json" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = "final_output.json";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Main pipeline runner ───────────────────────────────────────────────────────
async function runPipeline() {
  if (running) return;
  const input = ta.value.trim();
  if (!input) { ta.focus(); return; }

  running = true;
  runBtn.disabled  = true;
  ta.disabled      = true;
  runBtnLabel.textContent = "Running…";
  connError.setAttribute("hidden", "");
  stageEl.textContent = "";

  addBubble(input, "bubble-user");

  // Clear terminal, add cursor
  termScroll.innerHTML = "";
  const cursor = document.createElement("span");
  cursor.id = "cursor";
  termScroll.appendChild(cursor);

  // Hide old JSON
  jsonZone.setAttribute("hidden", "");
  jsonOpen = false;
  jsonBody.classList.remove("open");
  jsonChevron.classList.remove("open");

  setStatus("running");
  startElapsed();

  try {
    const response = await fetch("/run-pipeline", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ user_input: input }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer    = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by \n\n
      const parts = buffer.split("\n\n");
      buffer = parts.pop();               // keep incomplete last chunk

      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        const payload = part.slice(6);   // strip "data: "

        if (payload === "[DONE]") {
          // Pipeline finished cleanly
          $("cursor")?.remove();
          setStatus("done");
          stopElapsed();
          addBubble("✅ Pipeline complete — final_output.json ready above.", "bubble-ok");
          await fetchAndShowJson();
          _resetInput();
          return;
        }

        if (payload.startsWith("[ERROR]")) {
          appendLine(payload);
          continue;
        }

        // Unescape \\n sequences (lines with embedded newlines)
        const text = payload.replace(/\\n/g, "\n");
        for (const subline of text.split("\n")) {
          appendLine(subline);
        }
      }
    }

    // Stream ended without [DONE] sentinel
    $("cursor")?.remove();
    setStatus("done");
    stopElapsed();

  } catch (err) {
    $("cursor")?.remove();
    setStatus("error");
    stopElapsed();
    connError.removeAttribute("hidden");
    connErrMsg.textContent =
      `Connection error: ${err.message}. Make sure the FastAPI server is running.`;
    addBubble("❌ Pipeline failed — check server connection.", "bubble-err");
  }

  _resetInput();
}

function _resetInput() {
  running = false;
  runBtn.disabled = false;
  ta.disabled     = false;
  runBtnLabel.textContent = "Run pipeline";
  ta.value = "";
  ta.focus();
}

// ── Keyboard shortcut ─────────────────────────────────────────────────────────
ta.addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    runPipeline();
  }
});

jsonHeader.addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleJson(); }
});

// ── Settings modal ─────────────────────────────────────────────────────────────
function openSettings() {
  // Load current saved config into form
  fetch("/get-config")
    .then(r => r.json())
    .then(cfg => {
      providerSel.value  = cfg.provider  || "ollama";
      modelInput.value   = cfg.model     || "";
      baseUrlInput.value = cfg.base_url  || "";
      apikeyInput.value  = "";           // never pre-fill the key field
      apikeyInput.placeholder = cfg.api_key
        ? "API key saved — enter new one to replace"
        : "sk-… (leave blank to keep current)";
      saveStatus.setAttribute("hidden", "");
    })
    .catch(() => {});

  overlay.removeAttribute("hidden");
  modal.removeAttribute("hidden");
}

function closeSettings() {
  overlay.setAttribute("hidden", "");
  modal.setAttribute("hidden", "");
}

function onProviderChange() {
  const preset = PRESETS[providerSel.value];
  if (preset) {
    modelInput.value   = preset.model;
    baseUrlInput.value = preset.base_url;
  }
}

function toggleApiKeyVisibility() {
  apiKeyVisible       = !apiKeyVisible;
  apikeyInput.type    = apiKeyVisible ? "text" : "password";
}

async function saveSettings() {
  saveStatus.setAttribute("hidden", "");

  const provider = providerSel.value;
  const model    = modelInput.value.trim();
  const base_url = baseUrlInput.value.trim();
  const api_key  = apikeyInput.value.trim();  // empty = server keeps existing

  if (!model || !base_url) {
    showSaveStatus("Model name and Base URL are required.", false);
    return;
  }

  try {
    const res = await fetch("/save-config", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ provider, model, base_url, api_key }),
    });

    if (!res.ok) throw new Error(await res.text());

    showSaveStatus("Settings saved successfully.", true);
    providerBadge.textContent = `${provider} / ${model}`;
    setTimeout(closeSettings, 900);

  } catch (err) {
    showSaveStatus(`Save failed: ${err.message}`, false);
  }
}

function showSaveStatus(msg, ok) {
  saveStatus.textContent  = msg;
  saveStatus.className    = "save-status " + (ok ? "ok" : "err");
  saveStatus.removeAttribute("hidden");
}

// Close modal on Escape
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeSettings();
});