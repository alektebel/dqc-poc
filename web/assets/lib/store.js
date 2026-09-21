/* Revisions and controls: the API when there is one, the browser when
 * there is not.
 *
 * Both halves expose the same functions, so no screen has to know which
 * one it got. With the API configured the state is shared and durable;
 * without it, it lives in localStorage and belongs to this browser only.
 * The screens say which mode they are in — a reviewer who thinks their
 * validations are saved on a server when they are in a tab is a problem
 * waiting for a cleared cache.
 */

import { hasApi } from '../config.js';
import * as api from './api.js';

const KEY_REVISIONS = 'dqc.revisions';
const KEY_CHECKS = 'dqc.checks';

export const usingApi = () => hasApi();

function nowIso() {
  return new Date().toISOString().replace(/\.\d+Z$/, 'Z');
}

export function newId(prefix) {
  const random = Math.random().toString(16).slice(2, 8);
  return `${prefix}_${Date.now().toString(36)}${random}`;
}

// ── localStorage half ────────────────────────────────────────────────────────

function read(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || '[]');
  } catch (_) {
    return [];
  }
}

function write(key, rows) {
  try {
    window.localStorage.setItem(key, JSON.stringify(rows));
  } catch (_) {
    // QuotaExceededError: the examples of a big control are what fill this
    throw new Error(
      'No se pudo guardar en el navegador (espacio agotado). ' +
        'Configura la API o borra revisiones antiguas.',
    );
  }
}

// ── revisions ────────────────────────────────────────────────────────────────

export async function listRevisions() {
  if (usingApi()) return api.revisions.list();
  return read(KEY_REVISIONS).sort((a, b) =>
    String(b.created_at).localeCompare(String(a.created_at)),
  );
}

export async function getRevision(id) {
  if (usingApi()) return api.revisions.get(id);
  const found = read(KEY_REVISIONS).find((r) => r.revision_id === id);
  if (!found) throw new Error(`La revisión ${id} no existe en este navegador.`);
  return found;
}

export async function createRevision(revision) {
  const record = {
    ...revision,
    revision_id: revision.revision_id || newId('rev'),
    status: revision.status || 'pendiente',
    created_at: nowIso(),
    updated_at: nowIso(),
  };
  if (usingApi()) return api.revisions.create(record);
  write(KEY_REVISIONS, [...read(KEY_REVISIONS), record]);
  return record;
}

export async function updateRevision(id, patch) {
  if (usingApi()) {
    const current = await api.revisions.get(id);
    return api.revisions.update(id, { ...current, ...patch, updated_at: nowIso() });
  }
  const rows = read(KEY_REVISIONS);
  const index = rows.findIndex((r) => r.revision_id === id);
  if (index === -1) throw new Error(`La revisión ${id} no existe en este navegador.`);
  rows[index] = { ...rows[index], ...patch, updated_at: nowIso() };
  write(KEY_REVISIONS, rows);
  return rows[index];
}

export async function deleteRevision(id) {
  if (usingApi()) return api.revisions.remove(id);
  write(
    KEY_REVISIONS,
    read(KEY_REVISIONS).filter((r) => r.revision_id !== id),
  );
  write(
    KEY_CHECKS,
    read(KEY_CHECKS).filter((c) => c.revision_id !== id),
  );
  return { deleted: id };
}

// ── controls ─────────────────────────────────────────────────────────────────

export async function listChecks(revisionId) {
  if (usingApi()) return api.checks.list(revisionId);
  return read(KEY_CHECKS)
    .filter((c) => c.revision_id === revisionId)
    .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
}

export async function createCheck(revisionId, check) {
  const record = {
    ...check,
    check_id: check.check_id || newId('chk'),
    revision_id: revisionId,
    status: check.status || 'pending',
    created_at: nowIso(),
    updated_at: nowIso(),
  };
  if (usingApi()) return api.checks.create(revisionId, record);
  write(KEY_CHECKS, [...read(KEY_CHECKS), record]);
  return record;
}

export async function updateCheck(revisionId, checkId, patch) {
  if (usingApi()) {
    const current = (await api.checks.list(revisionId)).find(
      (c) => c.check_id === checkId,
    );
    return api.checks.update(revisionId, checkId, {
      ...(current || {}),
      ...patch,
      updated_at: nowIso(),
    });
  }
  const rows = read(KEY_CHECKS);
  const index = rows.findIndex((c) => c.check_id === checkId);
  if (index === -1) throw new Error(`El control ${checkId} no existe.`);
  rows[index] = { ...rows[index], ...patch, updated_at: nowIso() };
  write(KEY_CHECKS, rows);
  return rows[index];
}

export async function deleteCheck(revisionId, checkId) {
  if (usingApi()) return api.checks.remove(revisionId, checkId);
  write(
    KEY_CHECKS,
    read(KEY_CHECKS).filter((c) => c.check_id !== checkId),
  );
  return { deleted: checkId };
}
