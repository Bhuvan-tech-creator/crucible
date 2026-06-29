/**
 * static/js/main.js
 * Application entry point. Imports state, UI helpers, and API functions,
 * then wires up all events and drives the application flow.
 */

import { state }                        from "./state.js";
import * as UI                          from "./ui.js";
import { els }                          from "./ui.js";
import { setKey, analyzeDocument, startDebate } from "./api.js";

// ── Bootstrap ──────────────────────────────────────────────────────────────

UI.applyTheme(state.theme);
UI.updateKpis();
bindEvents();

// ── Event binding ──────────────────────────────────────────────────────────

function bindEvents() {
  els.themeToggle.addEventListener("click", onToggleTheme);
  els.saveKeyBtn.addEventListener("click", onSaveKey);
  els.documentFile.addEventListener("change", () => UI.renderFileMeta(els.documentFile.files[0]));
  els.analyzeBtn.addEventListener("click", onAnalyze);
  els.clearBtn.addEventListener("click", onClear);
  els.addAgentBtn.addEventListener("click", () => openAgentModal(null));
  els.runDebateBtn.addEventListener("click", onRunDebate);
  els.stopDebateBtn.addEventListener("click", onStopDebate);
  els.closeModalBtn.addEventListener("click", UI.closeModal);
  els.cancelAgentBtn.addEventListener("click", UI.closeModal);
  els.saveAgentBtn.addEventListener("click", onSaveAgent);
  els.agentModalBackdrop.addEventListener("click", (e) => {
    if (e.target === els.agentModalBackdrop) UI.closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && els.agentModalBackdrop.classList.contains("open")) UI.closeModal();
  });
}

// ── Handlers ───────────────────────────────────────────────────────────────

function onToggleTheme() {
  state.theme = state.theme === "dark" ? "light" : "dark";
  UI.applyTheme(state.theme);
}

async function onSaveKey() {
  const apiKey = els.apiKeyInput.value.trim();
  if (!apiKey) {
    UI.showToast("Enter a Groq API key first.", "error");
    return;
  }
  els.saveKeyBtn.disabled    = true;
  els.saveKeyBtn.textContent = "Saving…";
  try {
    await setKey(apiKey);
    state.apiKeySet = true;
    UI.setApiStatus("Groq key loaded", "ok");
    UI.showToast("Groq API key validated and saved.", "success");
  } catch (err) {
    UI.setApiStatus("API key error", "error");
    UI.showToast(err.message, "error", 4500);
  } finally {
    els.saveKeyBtn.disabled    = false;
    els.saveKeyBtn.textContent = "Save Key";
  }
}

async function onAnalyze() {
  const file = els.documentFile.files[0];
  if (!file) {
    UI.showToast("Choose a document before analyzing.", "error");
    return;
  }
  els.analyzeBtn.disabled    = true;
  els.analyzeBtn.textContent = "Analyzing…";
  UI.setDebateStatus("Analyzing document", true);

  try {
    const data = await analyzeDocument(file);
    // Persist into state
    state.documentText   = data.document_text   || "";
    state.documentType   = data.document_type   || "Engineering Document";
    state.projectSummary = data.project_summary || "";
    state.agents         = Array.isArray(data.agents) ? data.agents : [];
    state.messageCount   = 0;

    // Render
    UI.renderDocumentMeta(state.documentType, state.projectSummary);
    UI.renderDocumentText(state.documentText);
    renderAgentList();
    UI.setDebateStatus("Ready to debate", false);
    UI.showToast("Document analyzed — agents generated.", "success");
  } catch (err) {
    UI.setDebateStatus("Idle", false);
    UI.showToast(err.message, "error", 4500);
  } finally {
    els.analyzeBtn.disabled    = false;
    els.analyzeBtn.textContent = "Analyze Document";
  }
}

function onClear() {
  if (state.debateController) {
    state.debateController.abort();
    state.debateController = null;
  }
  // Reset state
  Object.assign(state, {
    currentFile:    null,
    documentText:   "",
    documentType:   "",
    projectSummary: "",
    agents:         [],
    messageCount:   0,
    debateRunning:  false,
  });
  // Reset UI
  els.documentFile.value = "";
  els.fileMeta.classList.add("hidden");
  els.documentSummaryCard.classList.add("hidden");
  els.documentCard.classList.add("hidden");
  els.agentControlsCard.classList.add("hidden");
  els.documentPreview.textContent  = "";
  els.projectSummaryText.textContent = "";
  els.summaryContent.textContent   = "No verdict yet.";
  els.runDebateBtn.disabled  = true;
  els.stopDebateBtn.disabled = true;
  UI.clearTimeline();
  UI.updateKpis();
  UI.setDebateStatus("Idle", false);
  UI.showToast("Workspace reset.", "success", 2200);
}

async function onRunDebate() {
  if (!state.documentText) {
    UI.showToast("Analyze a document first.", "error");
    return;
  }
  if (state.agents.length < 2) {
    UI.showToast("At least two agents are required.", "error");
    return;
  }

  state.debateRunning  = true;
  state.messageCount   = 0;
  els.summaryContent.textContent = "Debate in progress…";

  UI.clearTimeline();
  UI.updateKpis();
  UI.setDebateStatus("Debate running", true);
  els.runDebateBtn.disabled  = true;
  els.stopDebateBtn.disabled = false;

  const controller = new AbortController();
  state.debateController = controller;

  try {
    const response = await startDebate(
      state.documentText,
      state.agents,
      Number(els.roundCount.value),
      controller.signal
    );

    const reader  = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer    = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        const line = event.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const payload = line.slice(6);
        if (!payload.trim()) continue;
        handleSSEEvent(JSON.parse(payload));
      }
    }
  } catch (err) {
    if (err.name === "AbortError") {
      UI.showToast("Debate stream stopped.", "success");
    } else {
      UI.showToast(err.message || "Debate failed.", "error", 4500);
    }
  } finally {
    state.debateRunning    = false;
    state.debateController = null;
    els.runDebateBtn.disabled  = !state.documentText || state.agents.length < 2;
    els.stopDebateBtn.disabled = true;
    UI.setDebateStatus("Idle", false);
  }
}

function onStopDebate() {
  if (state.debateController) {
    state.debateController.abort();
  }
}

// ── SSE event dispatch ─────────────────────────────────────────────────────

function handleSSEEvent(data) {
  switch (data.type) {
    case "phase":
      UI.appendPhase(data.content);
      break;
    case "message":
      UI.appendMessage(data.message);
      state.messageCount += 1;
      UI.updateKpis();
      break;
    case "verdict":
      els.summaryContent.textContent = data.content;
      break;
    case "error":
      UI.appendPhase(`⚠ Error: ${data.content}`);
      UI.showToast(data.content, "error", 4500);
      break;
    case "done":
      UI.setDebateStatus("Debate complete", false);
      UI.showToast("Debate completed. Verdict is ready.", "success");
      break;
    default:
      break;
  }
}

// ── Agent modal ────────────────────────────────────────────────────────────

function openAgentModal(agent) {
  state.editingAgentId = agent ? agent.id : null;
  UI.fillModal(agent);
  UI.openModal(agent ? "Edit Agent" : "Add Custom Agent");
}

function onSaveAgent() {
  const data = UI.readModal();

  if (!data.name)              { UI.showToast("Agent name is required.",      "error"); return; }
  if (!data.description)       { UI.showToast("Description is required.",     "error"); return; }
  if (!data.skillset.length)   { UI.showToast("Add at least one skill.",      "error"); return; }

  const payload = {
    id:          state.editingAgentId || `agent_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name:        data.name,
    role:        data.role,
    icon:        data.icon,
    color:       data.color,
    description: data.description,
    skillset:    data.skillset,
  };

  const idx = state.agents.findIndex((a) => a.id === payload.id);
  if (idx >= 0) {
    state.agents[idx] = payload;
    UI.showToast("Agent updated.", "success");
  } else {
    state.agents.push(payload);
    UI.showToast("Agent added.", "success");
  }

  renderAgentList();
  UI.closeModal();
}

// ── Shared agent rendering helper ──────────────────────────────────────────

function renderAgentList() {
  UI.renderAgents(
    state.agents,
    (agent) => openAgentModal(agent),
    (id) => {
      const agent = state.agents.find((a) => a.id === id);
      state.agents = state.agents.filter((a) => a.id !== id);
      renderAgentList();
      if (agent) UI.showToast(`${agent.name} removed.`, "success");
    }
  );
  els.runDebateBtn.disabled =
    !state.documentText || state.agents.length < 2 || state.debateRunning;
  UI.updateKpis();
}