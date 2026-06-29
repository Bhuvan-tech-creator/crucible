/**
 * static/js/state.js
 * Single source of truth for all client-side application state.
 * Mutated directly — no framework, no reactivity layer needed at this scale.
 */

export const state = {
  /** Whether the Groq API key has been accepted by the server */
  apiKeySet: false,

  /** The File object from the file picker */
  currentFile: null,

  /** Full extracted text of the uploaded document */
  documentText: "",

  /** Short label describing the document type (from LLM) */
  documentType: "",

  /** 2–3 sentence project summary (from LLM) */
  projectSummary: "",

  /**
   * Array of agent objects.
   * Shape: { id, name, role, icon, color, description, skillset: string[] }
   */
  agents: [],

  /** ID of the agent currently being edited in the modal (null = new agent) */
  editingAgentId: null,

  /** AbortController for the active EventSource / fetch stream */
  debateController: null,

  /** Running count of messages received during the current debate session */
  messageCount: 0,

  /** True while a debate stream is in progress */
  debateRunning: false,

  /** "light" | "dark" — synced to <html data-theme="..."> */
  theme: window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
};