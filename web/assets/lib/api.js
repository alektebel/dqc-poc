/* The one API this frontend talks to. See docs/API_CONTRACT.md.
 *
 * Everything that needs a credential — Bedrock, DynamoDB — happens on the
 * other side of this URL. The browser knows a URL and, at most, a key that
 * only opens this endpoint.
 */

import { CONFIG, hasApi } from '../config.js';

export class ApiError extends Error {}

/** Not configured yet: callers turn this into "modo local", not a crash. */
export class NoApi extends Error {
  constructor() {
    super('No hay API configurada (web/assets/config.js).');
  }
}

async function request(path, { method = 'GET', body } = {}) {
  if (!hasApi()) throw new NoApi();

  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (CONFIG.API_KEY) headers[CONFIG.API_KEY_HEADER] = CONFIG.API_KEY;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONFIG.TIMEOUT_S * 1000);
  let res;
  try {
    res = await fetch(CONFIG.BASE_URL.replace(/\/$/, '') + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') {
      throw new ApiError(`La API no respondió en ${CONFIG.TIMEOUT_S}s.`);
    }
    // fetch fails this way for DNS, TLS and CORS alike; CORS is by far the
    // most common one when wiring a new endpoint
    throw new ApiError(
      `No se pudo contactar con la API (${err.message}). ` +
        'Si la URL es correcta, suele ser CORS: revisa docs/API_CONTRACT.md.',
    );
  }
  clearTimeout(timer);

  const text = await res.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch (_) {
    payload = text;
  }
  if (!res.ok) {
    const detail = (payload && payload.detail) || payload || res.statusText;
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return payload;
}

/** Rule + dictionary → query. The only call that reaches Bedrock. */
export function interpret({ regla, tabla, campos, valoresEjemplo, comentario }) {
  return request('/llm/interpret', {
    method: 'POST',
    body: {
      regla,
      tabla,
      campos,
      valores_ejemplo: valoresEjemplo || {},
      comentario: comentario || '',
    },
  });
}

/** What the detected rows have in common. Optional on the server side. */
export function explain(payload) {
  return request('/llm/explain', { method: 'POST', body: payload });
}

export const revisions = {
  list: () => request('/revisions'),
  get: (id) => request(`/revisions/${encodeURIComponent(id)}`),
  create: (revision) => request('/revisions', { method: 'POST', body: revision }),
  update: (id, revision) =>
    request(`/revisions/${encodeURIComponent(id)}`, { method: 'PUT', body: revision }),
  remove: (id) => request(`/revisions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};

export const checks = {
  list: (revisionId) => request(`/revisions/${encodeURIComponent(revisionId)}/checks`),
  create: (revisionId, check) =>
    request(`/revisions/${encodeURIComponent(revisionId)}/checks`, {
      method: 'POST',
      body: check,
    }),
  update: (revisionId, checkId, check) =>
    request(
      `/revisions/${encodeURIComponent(revisionId)}/checks/${encodeURIComponent(checkId)}`,
      { method: 'PUT', body: check },
    ),
  remove: (revisionId, checkId) =>
    request(
      `/revisions/${encodeURIComponent(revisionId)}/checks/${encodeURIComponent(checkId)}`,
      { method: 'DELETE' },
    ),
};
