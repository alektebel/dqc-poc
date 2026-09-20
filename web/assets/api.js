/* Shared browser helpers: the API lives on the same origin as these pages
   (FastAPI serves /app), so every path is relative and no CORS is involved. */

const API = '';

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch (_) { body = text; }
  if (!res.ok) {
    const detail = (body && body.detail) || body || res.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return body;
}

function apiJson(path, method, payload) {
  return api(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/** Read one query-string parameter ("?rev=rev_x" → revision id). */
function param(name) {
  return new URLSearchParams(window.location.search).get(name) || '';
}

/** Send the user back to the listing when the page needs a revision and
    the URL carries none — every step but the first is revision-scoped. */
function requireRevision() {
  const rev = param('rev');
  if (!rev) window.location.href = 'home.html';
  return rev;
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** "2026-09-12T15:30:00Z" → "2026-09-12 15:30" (local reading, no library). */
function formatDate(iso) {
  if (!iso) return '–';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
         `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Consume a Server-Sent Events response opened with POST (fetch, not
    EventSource, which is GET-only). Calls onEvent(name, data) per frame. */
async function consumeStream(path, formData, onEvent) {
  const res = await fetch(API + path, { method: 'POST', body: formData });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try { detail = JSON.parse(text).detail || text; } catch (_) { /* raw */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let name = 'message';
      const data = [];
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) name = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trim());
      }
      if (data.length) onEvent(name, JSON.parse(data.join('')));
    }
  }
}
