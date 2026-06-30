/**
 * static/js/api.js
 * All fetch calls to the Flask backend.
 * Updated to support multi-file uploads via getlist("files").
 */

const BASE = "";  // Same origin

/**
 * POST /api/set-key
 */
export async function setKey(apiKey) {
  const res  = await fetch(`${BASE}/api/set-key`, {
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
 * Now accepts a FileList or array of File objects.
 *
 * @param {FileList|File[]} files
 * @returns {Promise<{document_text, document_type, project_summary, agents, file_count, file_names}>}
 */
export async function analyzeDocument(files) {
  const formData = new FormData();

  // Normalise to an iterable
  const fileArray = files instanceof FileList ? Array.from(files) : [].concat(files);

  fileArray.forEach((f) => {
    formData.append("files", f);
  });

  const res  = await fetch(`${BASE}/api/analyze`, {
    method: "POST",
    body:   formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Analysis failed.");
  return data;
}

/**
 * POST /api/debate
 * Start a streaming debate session.
 *
 * @param {string}      documentText
 * @param {object[]}    agents
 * @param {number}      rounds
 * @param {AbortSignal} signal
 * @returns {Promise<Response>}
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