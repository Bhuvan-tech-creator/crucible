/**
 * static/js/ui.js
 * DOM helper functions — rendering, toasts, KPI updates, timeline management.
 * No state mutations happen here; callers pass the values they want rendered.
 */

import { state } from "./state.js";

/* ── Element cache ──────────────────────────────────────────────────── */

export const els = {
  apiKeyInput:           document.getElementById("apiKeyInput"),
  saveKeyBtn:            document.getElementById("saveKeyBtn"),
  apiStatus:             document.getElementById("apiStatus"),
  themeToggle:           document.getElementById("themeToggle"),
  documentFile:          document.getElementById("documentFile"),
  analyzeBtn:            document.getElementById("analyzeBtn"),
  clearBtn:              document.getElementById("clearBtn"),
  fileMeta:              document.getElementById("fileMeta"),
  documentSummaryCard:   document.getElementById("documentSummaryCard"),
  docTypeChip:           document.getElementById("docTypeChip"),
  agentCountChip:        document.getElementById("agentCountChip"),
  projectSummaryText:    document.getElementById("projectSummaryText"),
  documentCard:          document.getElementById("documentCard"),
  documentPreview:       document.getElementById("documentPreview"),
  agentControlsCard:     document.getElementById("agentControlsCard"),
  agentList:             document.getElementById("agentList"),
  addAgentBtn:           document.getElementById("addAgentBtn"),
  roundCount:            document.getElementById("roundCount"),
  runDebateBtn:          document.getElementById("runDebateBtn"),
  stopDebateBtn:         document.getElementById("stopDebateBtn"),
  debateStatus:          document.getElementById("debateStatus"),
  timeline:              document.getElementById("timeline"),
  summaryContent:        document.getElementById("summaryContent"),
  kpiAgents:             document.getElementById("kpiAgents"),
  kpiMessages:           document.getElementById("kpiMessages"),
  agentModalBackdrop:    document.getElementById("agentModalBackdrop"),
  closeModalBtn:         document.getElementById("closeModalBtn"),
  cancelAgentBtn:        document.getElementById("cancelAgentBtn"),
  saveAgentBtn:          document.getElementById("saveAgentBtn"),
  agentModalTitle:       document.getElementById("agentModalTitle"),
  agentNameInput:        document.getElementById("agentNameInput"),
  agentRoleInput:        document.getElementById("agentRoleInput"),
  agentDescriptionInput: document.getElementById("agentDescriptionInput"),
  agentSkillsInput:      document.getElementById("agentSkillsInput"),
  agentIconInput:        document.getElementById("agentIconInput"),
  agentColorInput:       document.getElementById("agentColorInput"),
  toastWrap:             document.getElementById("toastWrap"),
};

/* ── Escape ─────────────────────────────────────────────────────────── */

export function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* ── Theme ──────────────────────────────────────────────────────────── */

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  els.themeToggle.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
  els.themeToggle.setAttribute(
    "aria-label",
    theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
  );
}

/* ── Status pills ───────────────────────────────────────────────────── */

export function setApiStatus(text, tone = "ok") {
  els.apiStatus.innerHTML = `<span class="status-dot"></span><span>${esc(text)}</span>`;
  const isErr = tone === "error";
  els.apiStatus.style.color           = isErr ? "#ff9aa5" : "var(--color-primary)";
  els.apiStatus.style.background      = isErr ? "rgba(255,107,122,0.12)" : "rgba(76,201,216,0.10)";
  els.apiStatus.style.borderColor     = isErr ? "rgba(255,107,122,0.22)" : "rgba(76,201,216,0.18)";
}

export function setDebateStatus(text, running = false) {
  els.debateStatus.innerHTML = `<span class="status-dot"></span><span>${esc(text)}</span>`;
  els.debateStatus.style.color        = running ? "var(--color-warning)" : "var(--color-primary)";
  els.debateStatus.style.background   = running ? "rgba(255,176,77,0.12)" : "rgba(76,201,216,0.10)";
  els.debateStatus.style.borderColor  = running ? "rgba(255,176,77,0.25)" : "rgba(76,201,216,0.18)";
}

/* ── Toasts ─────────────────────────────────────────────────────────── */

export function showToast(message, type = "success", ttl = 3200) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  els.toastWrap.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 220);
  }, ttl);
}

/* ── KPI counters ───────────────────────────────────────────────────── */

export function updateKpis() {
  els.kpiAgents.textContent   = String(state.agents.length);
  els.kpiMessages.textContent = String(state.messageCount);
  els.agentCountChip.textContent = `${state.agents.length} Agent${state.agents.length === 1 ? "" : "s"}`;
}

/* ── File metadata ──────────────────────────────────────────────────── */

export function renderFileMeta(file) {
  if (!file) return;
  const kb = (file.size / 1024).toFixed(1);
  els.fileMeta.innerHTML = `
    <div class="stack" style="gap:0.6rem;">
      <strong>Selected File</strong>
      <div class="chips">
        <div class="chip">${esc(file.name)}</div>
        <div class="chip">${kb} KB</div>
        <div class="chip">${esc(file.type || "text/plain")}</div>
      </div>
    </div>`;
  els.fileMeta.classList.remove("hidden");
}

/* ── Document analysis results ──────────────────────────────────────── */

export function renderDocumentMeta(documentType, projectSummary) {
  els.docTypeChip.textContent       = documentType;
  els.projectSummaryText.textContent = projectSummary || "No summary returned.";
  els.documentSummaryCard.classList.remove("hidden");
}

export function renderDocumentText(text) {
  els.documentPreview.textContent = text;
  els.documentCard.classList.remove("hidden");
}

/* ── Agent list ─────────────────────────────────────────────────────── */

export function renderAgents(agents, onEdit, onDelete) {
  if (!agents.length) {
    els.agentList.innerHTML = `
      <div class="empty-state">
        <div class="symbol">🧩</div>
        <div>
          <strong>No agents configured.</strong>
          <p class="muted">Analyze a document or add a custom specialist manually.</p>
        </div>
      </div>`;
  } else {
    els.agentList.innerHTML = "";
    agents.forEach((agent) => {
      const card = document.createElement("article");
      card.className = "agent-card";
      const label = humanRole(agent.role);
      card.innerHTML = `
        <div class="agent-card-header">
          <div style="display:flex;gap:0.9rem;min-width:0;">
            <div class="agent-pill" style="background:${esc(agent.color)};">${esc(agent.icon)}</div>
            <div class="agent-name-wrap">
              <h4>${esc(agent.name)}</h4>
              <div class="agent-role">${esc(label)}</div>
            </div>
          </div>
          <div class="agent-actions">
            <button class="icon-btn" type="button" aria-label="Edit ${esc(agent.name)}"
              data-action="edit" data-id="${esc(agent.id)}">✎</button>
            <button class="icon-btn" type="button" aria-label="Delete ${esc(agent.name)}"
              data-action="delete" data-id="${esc(agent.id)}">🗑</button>
          </div>
        </div>
        <p class="muted">${esc(agent.description)}</p>
        <div class="skill-list">
          ${agent.skillset.map((s) => `<span class="skill-tag">${esc(s)}</span>`).join("")}
        </div>`;
      els.agentList.appendChild(card);
    });
  }

  // Wire click delegation
  els.agentList.onclick = (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id     = btn.dataset.id;
    const action = btn.dataset.action;
    const agent  = agents.find((a) => a.id === id);
    if (!agent) return;
    if (action === "edit")   onEdit(agent);
    if (action === "delete") onDelete(id);
  };

  els.agentControlsCard.classList.remove("hidden");
  updateKpis();
}

/* ── Timeline ───────────────────────────────────────────────────────── */

export function clearTimeline() {
  els.timeline.innerHTML = `
    <div class="empty-state">
      <div class="symbol">🧠</div>
      <div>
        <strong>Nothing has debated yet.</strong>
        <p class="muted">Analyze a document, fine-tune the agent list, and start the discussion.</p>
      </div>
    </div>`;
}

export function appendPhase(content) {
  removeTimelineEmpty();
  const phase = document.createElement("div");
  phase.className = "phase-card";
  phase.textContent = content;
  els.timeline.appendChild(phase);
  scrollBottom();
}

export function appendMessage(msg) {
  removeTimelineEmpty();
  const card = document.createElement("article");
  card.className = "message-card";
  card.innerHTML = `
    <div class="message-head">
      <div class="message-agent">
        <div class="message-avatar" style="background:${esc(msg.agent_color)};">${esc(msg.agent_icon)}</div>
        <div>
          <strong>${esc(msg.agent_name)}</strong>
          <span>${esc(msg.phase)}</span>
        </div>
      </div>
      <span class="chip">Round ${esc(String(msg.round))}</span>
    </div>
    <div class="message-content">${esc(msg.content)}</div>`;
  els.timeline.appendChild(card);
  scrollBottom();
}

function removeTimelineEmpty() {
  const empty = els.timeline.querySelector(".empty-state");
  if (empty) empty.remove();
}

function scrollBottom() {
  requestAnimationFrame(() => {
    const body = els.timeline.parentElement;
    body.scrollTop = body.scrollHeight;
  });
}

/* ── Modal helpers ──────────────────────────────────────────────────── */

export function openModal(title) {
  els.agentModalTitle.textContent = title;
  els.agentModalBackdrop.classList.add("open");
  els.agentModalBackdrop.setAttribute("aria-hidden", "false");
  els.agentNameInput.focus();
}

export function closeModal() {
  els.agentModalBackdrop.classList.remove("open");
  els.agentModalBackdrop.setAttribute("aria-hidden", "true");
}

export function fillModal(agent) {
  els.agentNameInput.value        = agent?.name        ?? "";
  els.agentRoleInput.value        = toModalRole(agent?.role ?? "domain");
  els.agentDescriptionInput.value = agent?.description ?? "";
  els.agentSkillsInput.value      = agent?.skillset?.join(", ") ?? "";
  els.agentIconInput.value        = agent?.icon        ?? "🧪";
  els.agentColorInput.value       = safeColor(agent?.color ?? "#8e44ad");
}

export function readModal() {
  return {
    name:        els.agentNameInput.value.trim(),
    role:        fromModalRole(els.agentRoleInput.value),
    description: els.agentDescriptionInput.value.trim(),
    skillset:    els.agentSkillsInput.value.split(",").map((s) => s.trim()).filter(Boolean),
    icon:        els.agentIconInput.value.trim() || "🧪",
    color:       els.agentColorInput.value,
  };
}

/* ── Internal helpers ───────────────────────────────────────────────── */

function humanRole(role) {
  if (role === "failure")    return "Failure Advocate";
  if (role === "success")    return "Success Advocate";
  return "Domain Specialist";
}

function toModalRole(role) {
  if (role === "failure" || role === "success") return role;
  return "domain";
}

function fromModalRole(value) {
  if (value === "failure" || value === "success") return value;
  return "specialist";
}

function safeColor(color) {
  if (color && color.startsWith("#") && (color.length === 7 || color.length === 4)) return color;
  return "#8e44ad";
}