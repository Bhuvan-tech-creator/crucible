/**
 * static/js/api.js
 * All fetch calls to the Flask backend, returning parsed data or throwing errors.
 * Keeps the network layer isolated so main.js stays free of raw fetch logic.
 */

const BASE = "";  // Same origin

/**
 * POST /api/set-key
 * Send a Groq API key to the backend for in-memory storage.
 * @param {string} apiKey
 * @returns {Promise<{status: string, message: string}>}
 */
export async function setKey(apiKey) {
  const res = await fetch(`${BASE}/api/set-key`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ api_key: apiKey }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || "Failed to save API key.");
  return data;
}

/**
 * POST /api/analyze
 * Upload a file and receive the extracted text + generated agent roster.
 * @param {File} file
 * @returns {Promise<{document_text, document_type, project_summary, agents}>}
 */
export async function analyzeDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/api/analyze`, {
    method: "POST",
    body:   formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Analysis failed.");
  return data;
}

/**
 * POST /api/debate
 * Start a streaming debate session. Returns a ReadableStream.
 * Callers are responsible for reading and parsing the SSE events.
 *
 * @param {string}   documentText  Extracted document text
 * @param {object[]} agents        Agent roster
 * @param {number}   rounds        Number of cross-examination rounds
 * @param {AbortSignal} signal     From an AbortController to cancel the stream
 * @returns {Promise<Response>}    The raw streaming Response
 */
export async function startDebate(documentText, agents, rounds, signal) {
  const res = await fetch(`${BASE}/api/debate`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ document_text: documentText, agents, rounds }),
    signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text();
    throw new Error(text || "Could not start debate stream.");
  }
  return res;
}