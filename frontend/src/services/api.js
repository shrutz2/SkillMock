// Central API client. Base URL defaults to the CRA dev proxy (package.json),
// override with REACT_APP_API_URL for production builds.
const BASE = process.env.REACT_APP_API_URL || "";

// Session token issued at upload. Held in memory only - it is the key to the
// uploaded resume, so it is never written to localStorage.
let sessionToken = null;

export function setSessionToken(token) {
  sessionToken = token || null;
}

function authHeaders(extra = {}) {
  return sessionToken
    ? { ...extra, Authorization: `Bearer ${sessionToken}` }
    : extra;
}

async function handle(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

export async function uploadResume(file) {
  const form = new FormData();
  form.append("resume", file);
  const res = await fetch(`${BASE}/api/resume/upload`, {
    method: "POST",
    body: form,
  });
  const data = await handle(res);
  setSessionToken(data.session_token);
  return data;
}

export async function getReport(sessionId, jobDescription) {
  const res = await fetch(`${BASE}/api/resume/report`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ session_id: sessionId, job_description: jobDescription || "" }),
  });
  return handle(res);
}

export async function generateQuestions(sessionId, roleLevel) {
  const res = await fetch(`${BASE}/api/questions/generate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ session_id: sessionId, role_level: roleLevel }),
  });
  return handle(res);
}

export async function evaluateAnswer(questionId, answerText) {
  const res = await fetch(`${BASE}/api/answers/evaluate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question_id: questionId, answer_text: answerText }),
  });
  return handle(res);
}

export async function getSummary(sessionId) {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/summary`, {
    headers: authHeaders(),
  });
  return handle(res);
}
