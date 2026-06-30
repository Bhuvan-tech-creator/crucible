/**
 * static/js/main.js
 * Crucible — full frontend controller.
 *
 * Stage system:
 *   "upload"  — before document is analysed
 *   "debate"  — while debate is running / after it starts
 *   "verdict" — after debate completes and verdict is available
 */

// ── DOM refs ────────────────────────────────────────────────────────────────

const appShell            = document.getElementById('appShell');
const themeToggle         = document.getElementById('themeToggle');

const documentFile        = document.getElementById('documentFile');
const analyzeBtn          = document.getElementById('analyzeBtn');
const clearBtn            = document.getElementById('clearBtn');
const fileMeta            = document.getElementById('fileMeta');
const documentSummaryCard = document.getElementById('documentSummaryCard');
const docTypeChip         = document.getElementById('docTypeChip');
const agentCountChip      = document.getElementById('agentCountChip');
const projectSummaryText  = document.getElementById('projectSummaryText');
const documentCard        = document.getElementById('documentCard');
const documentPreview     = document.getElementById('documentPreview');
const agentControlsCard   = document.getElementById('agentControlsCard');
const agentList           = document.getElementById('agentList');
const addAgentBtn         = document.getElementById('addAgentBtn');

const runDebateBtn        = document.getElementById('runDebateBtn');
const stopDebateBtn       = document.getElementById('stopDebateBtn');
const roundCount          = document.getElementById('roundCount');
const debateStatus        = document.getElementById('debateStatus');
const timeline            = document.getElementById('timeline');
const kpiAgents           = document.getElementById('kpiAgents');
const kpiMessages         = document.getElementById('kpiMessages');

const summaryContent      = document.getElementById('summaryContent');

const agentModalBackdrop    = document.getElementById('agentModalBackdrop');
const agentNameInput        = document.getElementById('agentNameInput');
const agentRoleInput        = document.getElementById('agentRoleInput');
const agentDescriptionInput = document.getElementById('agentDescriptionInput');
const agentSkillsInput      = document.getElementById('agentSkillsInput');
const agentIconInput        = document.getElementById('agentIconInput');
const agentColorInput       = document.getElementById('agentColorInput');
const saveAgentBtn          = document.getElementById('saveAgentBtn');
const cancelAgentBtn        = document.getElementById('cancelAgentBtn');
const closeModalBtn         = document.getElementById('closeModalBtn');

const toastWrap = document.getElementById('toastWrap');
const crumbs    = document.querySelectorAll('.crumb');

// ── State ───────────────────────────────────────────────────────────────────

let agents       = [];
let documentText = '';
let messageCount = 0;
let activeStream = null;

// ── Stage management ────────────────────────────────────────────────────────

function setStage(stage) {
  appShell.setAttribute('data-stage', stage);
  crumbs.forEach(c => c.classList.toggle('active', c.dataset.crumb === stage));
}

// ── Theme ───────────────────────────────────────────────────────────────────

(function initTheme() {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(prefersDark ? 'dark' : 'light');
})();

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  applyTheme(current === 'dark' ? 'light' : 'dark');
});

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  themeToggle.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
}

// ── File selection → immediate preview ───────────────────────────────────────
// Shows file chips as soon as the user picks files, before clicking Analyze.

documentFile.addEventListener('change', () => {
  const files = Array.from(documentFile.files);
  if (!files.length) {
    fileMeta.classList.add('hidden');
    fileMeta.innerHTML = '';
    analyzeBtn.disabled = true;
    return;
  }
  renderFileMeta(files);
  analyzeBtn.disabled = false;
});

function renderFileMeta(files) {
  const totalBytes = files.reduce((s, f) => s + f.size, 0);
  const chips = files.map(f => {
    const ext  = f.name.split('.').pop().toLowerCase();
    const icon = fileIcon(ext);
    return `<div class="chip file-chip">
      <span>${icon}</span>
      <span class="chip-filename">${escapeHTML(f.name)}</span>
      <span class="chip-size">${formatBytes(f.size)}</span>
    </div>`;
  }).join('');

  fileMeta.innerHTML = `
    <div class="file-meta-inner">
      <div class="file-meta-summary">
        <strong>${files.length} file${files.length > 1 ? 's' : ''} selected</strong>
        <span class="chip">${formatBytes(totalBytes)} total</span>
      </div>
      <div class="chips file-chips">${chips}</div>
    </div>`;
  fileMeta.classList.remove('hidden');
}

function fileIcon(ext) {
  const map = {
    pdf: '📄', docx: '📝', doc: '📝',
    txt: '📃', md: '📃', csv: '📊',
    stl: '🧊', obj: '🧊', gltf: '🧊', glb: '🧊',
    ply: '🧊', '3mf': '🧊', step: '🧊', stp: '🧊',
  };
  return map[ext] || '📎';
}

// ── Analyze document ──────────────────────────────────────────────────────────

analyzeBtn.addEventListener('click', async () => {
  const files = Array.from(documentFile.files);
  if (!files.length) { toast('Please select at least one file first.', 'error'); return; }

  setAnalyzeLoading(true);

  // Append every file under the key "files" so the backend receives all of them
  const form = new FormData();
  files.forEach(f => form.append('files', f));

  try {
    const res  = await fetch('/api/analyze', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) { toast(data.error || 'Analysis failed.', 'error'); return; }

    documentText = data.document_text;
    agents       = data.agents || [];

    // Summary card
    docTypeChip.textContent        = data.document_type    || 'Engineering Document';
    agentCountChip.textContent     = `${agents.length} agent${agents.length !== 1 ? 's' : ''}`;
    projectSummaryText.textContent = data.project_summary  || '';

    // Remove any stale merge chip, then add one if multi-file
    const stale = documentSummaryCard.querySelector('.merge-chip');
    if (stale) stale.remove();
    if (data.file_count && data.file_count > 1) {
      const chip = document.createElement('div');
      chip.className   = 'chip merge-chip';
      chip.textContent = `${data.file_count} files merged`;
      docTypeChip.parentElement.appendChild(chip);
    }

    documentSummaryCard.classList.remove('hidden');

    // Extracted text preview (first 3000 chars)
    documentPreview.textContent =
      documentText.slice(0, 3000) + (documentText.length > 3000 ? '\n\n… (truncated for display)' : '');
    documentCard.classList.remove('hidden');

    renderAgentList();
    agentControlsCard.classList.remove('hidden');
    kpiAgents.textContent = agents.length;

    const label = (data.file_count > 1) ? `${data.file_count} files merged` : 'Document analysed';
    toast(`${label} — ${agents.length} agents ready.`, 'success');

  } catch (err) {
    toast(`Network error: ${err.message}`, 'error');
  } finally {
    setAnalyzeLoading(false);
  }
});

function setAnalyzeLoading(on) {
  analyzeBtn.disabled    = on;
  analyzeBtn.textContent = on ? 'Analysing…' : 'Analyze Document';
}

// ── Clear / reset ─────────────────────────────────────────────────────────────

clearBtn.addEventListener('click', () => {
  if (activeStream) { activeStream.abort(); activeStream = null; }

  documentFile.value  = '';
  documentText        = '';
  agents              = [];
  messageCount        = 0;

  fileMeta.innerHTML  = '';
  fileMeta.classList.add('hidden');
  documentSummaryCard.classList.add('hidden');
  documentCard.classList.add('hidden');
  agentControlsCard.classList.add('hidden');
  agentList.innerHTML = '';

  const stale = documentSummaryCard.querySelector('.merge-chip');
  if (stale) stale.remove();

  timeline.innerHTML  = emptyTimelineHTML();
  summaryContent.textContent = 'No verdict yet.';
  summaryContent.classList.add('muted');

  kpiAgents.textContent   = '0';
  kpiMessages.textContent = '0';

  runDebateBtn.disabled   = true;
  runDebateBtn.classList.remove('btn-cta');
  stopDebateBtn.disabled  = true;

  setStatus('Idle', 'idle');
  setStage('upload');
});

// ── Agent list rendering ──────────────────────────────────────────────────────

function renderAgentList() {
  agentList.innerHTML = '';
  agents.forEach((agent, idx) => agentList.appendChild(buildAgentCard(agent, idx)));

  // Highlight Run Debate as the obvious next step once agents are ready
  const ready = documentText && agents.length >= 2;
  runDebateBtn.disabled = !ready;
  runDebateBtn.classList.toggle('btn-cta', !!ready);
}

function buildAgentCard(agent, idx) {
  const card = document.createElement('div');
  card.className = 'agent-card';

  const roleLabel = {
    failure:    'Failure Advocate',
    success:    'Success Advocate',
    domain:     'Domain Specialist',
    specialist: 'Domain Specialist',
  }[agent.role] || agent.role;

  card.innerHTML = `
    <div class="agent-card-header">
      <div style="display:flex; align-items:start; gap:var(--space-3); min-width:0;">
        <div class="agent-pill" style="background:${escapeHTML(agent.color)}">${escapeHTML(agent.icon)}</div>
        <div class="agent-name-wrap">
          <h4>${escapeHTML(agent.name)}</h4>
          <div class="agent-role">${roleLabel}</div>
        </div>
      </div>
      <div class="agent-actions">
        <button class="btn btn-ghost" data-action="remove" data-idx="${idx}"
          style="font-size:var(--text-xs); min-height:2rem; padding:0 0.7rem;">Remove</button>
      </div>
    </div>
    ${agent.description ? `<p class="muted">${escapeHTML(agent.description)}</p>` : ''}
    <div class="skill-list">
      ${(agent.skillset || []).map(s => `<span class="skill-tag">${escapeHTML(s)}</span>`).join('')}
    </div>`;

  card.querySelector('[data-action="remove"]').addEventListener('click', () => {
    agents.splice(idx, 1);
    kpiAgents.textContent = agents.length;
    renderAgentList();
    if (agents.length < 2) {
      runDebateBtn.disabled = true;
      runDebateBtn.classList.remove('btn-cta');
    }
  });

  return card;
}

// ── Add Agent modal ───────────────────────────────────────────────────────────

addAgentBtn.addEventListener('click',    openModal);
closeModalBtn.addEventListener('click',  closeModal);
cancelAgentBtn.addEventListener('click', closeModal);
agentModalBackdrop.addEventListener('click', e => {
  if (e.target === agentModalBackdrop) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && agentModalBackdrop.classList.contains('open')) closeModal();
});

function openModal() {
  agentNameInput.value        = '';
  agentDescriptionInput.value = '';
  agentSkillsInput.value      = '';
  agentIconInput.value        = '🧪';
  agentColorInput.value       = '#8e44ad';
  agentRoleInput.value        = 'domain';
  agentModalBackdrop.classList.add('open');
  agentModalBackdrop.setAttribute('aria-hidden', 'false');
  agentNameInput.focus();
}

function closeModal() {
  agentModalBackdrop.classList.remove('open');
  agentModalBackdrop.setAttribute('aria-hidden', 'true');
}

saveAgentBtn.addEventListener('click', () => {
  const name = agentNameInput.value.trim();
  if (!name) { toast('Agent name is required.', 'error'); return; }

  const skillset = agentSkillsInput.value
    .split(',').map(s => s.trim()).filter(Boolean);

  agents.push({
    id:          `custom_${Date.now()}`,
    name,
    role:        agentRoleInput.value,
    icon:        agentIconInput.value || '🤖',
    color:       agentColorInput.value,
    description: agentDescriptionInput.value.trim(),
    skillset,
  });

  kpiAgents.textContent = agents.length;
  renderAgentList();
  if (agents.length >= 2) {
    runDebateBtn.disabled = false;
    runDebateBtn.classList.add('btn-cta');
  }
  agentControlsCard.classList.remove('hidden');
  closeModal();
  toast(`Agent "${escapeHTML(name)}" added.`, 'success');
});

// ── Run debate ────────────────────────────────────────────────────────────────

runDebateBtn.addEventListener('click', startDebate);

async function startDebate() {
  if (!documentText)     { toast('No document loaded.', 'error');      return; }
  if (agents.length < 2) { toast('Need at least 2 agents.', 'error'); return; }

  setStage('debate');
  messageCount           = 0;
  timeline.innerHTML     = '';
  summaryContent.textContent = 'Debate in progress…';
  summaryContent.classList.add('muted');

  runDebateBtn.disabled  = true;
  runDebateBtn.classList.remove('btn-cta');
  stopDebateBtn.disabled = false;
  setStatus('Running…', 'running');

  activeStream = new AbortController();

  try {
    const res = await fetch('/api/debate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_text: documentText,
        agents,
        rounds: parseInt(roundCount.value, 10),
      }),
      signal: activeStream.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toast(err.error || 'Debate request failed.', 'error');
      resetDebateControls();
      return;
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop();

      for (const raw of events) {
        const line = raw.split('\n').find(l => l.startsWith('data:'));
        if (!line) continue;
        try { handleSSE(JSON.parse(line.slice(5).trim())); }
        catch (_) {}
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') toast(`Stream error: ${err.message}`, 'error');
  } finally {
    resetDebateControls();
    activeStream = null;
  }
}

function handleSSE(ev) {
  switch (ev.type) {
    case 'phase':
      timeline.appendChild(buildPhaseCard(ev.content));
      scrollTimeline();
      break;
    case 'message':
      messageCount++;
      kpiMessages.textContent = messageCount;
      timeline.appendChild(buildMessageCard(ev.message));
      scrollTimeline();
      break;
    case 'verdict':
      summaryContent.textContent = ev.content;
      summaryContent.classList.remove('muted');
      setStage('verdict');
      break;
    case 'error':
      toast(ev.content, 'error');
      break;
    case 'done':
      setStatus('Complete', 'done');
      toast('Debate complete — verdict ready.', 'success');
      break;
  }
}

stopDebateBtn.addEventListener('click', () => {
  if (activeStream) { activeStream.abort(); activeStream = null; }
  resetDebateControls();
  setStatus('Stopped', 'idle');
  toast('Debate stopped.', 'error');
});

function resetDebateControls() {
  runDebateBtn.disabled  = false;
  stopDebateBtn.disabled = true;
}

// ── Timeline builders ─────────────────────────────────────────────────────────

function buildPhaseCard(label) {
  const el = document.createElement('div');
  el.className   = 'phase-card';
  el.textContent = label;
  return el;
}

function buildMessageCard(msg) {
  const el = document.createElement('div');
  el.className = 'message-card';
  el.innerHTML = `
    <div class="message-head">
      <div class="message-agent">
        <div class="message-avatar" style="background:${escapeHTML(msg.agent_color)}">${escapeHTML(msg.agent_icon)}</div>
        <div>
          <strong>${escapeHTML(msg.agent_name)}</strong>
          <span>${escapeHTML(msg.phase)}</span>
        </div>
      </div>
    </div>
    <div class="message-content">${escapeHTML(msg.content)}</div>`;
  return el;
}

function scrollTimeline() {
  const body = timeline.closest('.panel-body');
  if (body) body.scrollTop = body.scrollHeight;
}

function emptyTimelineHTML() {
  return `
    <div class="empty-state">
      <div class="symbol">🧠</div>
      <div>
        <strong>Nothing has debated yet.</strong>
        <p class="muted">Analyze a document, configure agents, and start.</p>
      </div>
    </div>`;
}

// ── Status pill ───────────────────────────────────────────────────────────────

function setStatus(label, state) {
  const span = debateStatus.querySelector('span:last-child');
  if (span) span.textContent = label;
  debateStatus.style.setProperty('--status-color',
    state === 'running' ? 'var(--color-warning)' :
    state === 'done'    ? 'var(--color-success)'  :
                          'var(--color-primary)'
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function toast(message, type = 'info') {
  const el = document.createElement('div');
  el.className   = `toast ${type}`;
  el.textContent = message;
  toastWrap.appendChild(el);
  setTimeout(() => {
    el.style.opacity   = '0';
    el.style.transform = 'translateY(4px)';
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function formatBytes(bytes) {
  if (bytes < 1024)    return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function escapeHTML(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Boot ──────────────────────────────────────────────────────────────────────

setStage('upload');
analyzeBtn.disabled = true;