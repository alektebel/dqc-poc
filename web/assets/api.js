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
