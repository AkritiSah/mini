export const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export async function request(path, options = {}) {
  let response;
  try { response = await fetch(`${BASE}/api${path}`, options); }
  catch { throw new Error('Cannot reach the backend. Start the application with run.ps1.'); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.message ||
      (Array.isArray(detail) ? detail.map(e => e.msg).join('; ') : 'The request could not be completed.'));
  }
  return data;
}

export const api = {
  health: () => request('/health'),
  documents: () => request('/documents'),
  upload: data => request('/documents/upload', { method: 'POST', body: data }),
  job: id => request(`/jobs/${encodeURIComponent(id)}`),
  remove: id => request(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  reindex: id => request(`/documents/${encodeURIComponent(id)}/reindex`, { method: 'POST' }),
  source: id => request(`/sources/${encodeURIComponent(id)}`),
  chat: body => request('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
};
export const fileUrl = id => `${BASE}/api/documents/${encodeURIComponent(id)}/file`;
export function safeUrl(value) {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}
