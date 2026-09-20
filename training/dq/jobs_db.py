"""Batch runs, one row per rule.

A batch used to be a Server-Sent Events stream: the work happened inside
the request, and if the browser went away the progress went with it.
A job is the same work made observable from outside — every rule has a
row that says where it got to, so the screen polls instead of holding a
connection open, and a run survives a reload.

That is also the shape the work needs in order to be split up: one row
per rule is one invocation per rule, whatever ends up doing the invoking
(a thread here, a Step Functions Map state in AWS).

Lives in the same SQLite file as the checks and the revisions.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from training.dq import checks_db

JOB_STATUSES = ("pendiente", "en_curso", "completado", "error")
ITEM_STATUSES = ("pendiente", "en_curso", "completado", "ambigua", "error")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pendiente'
                CHECK (status IN ('pendiente','en_curso','completado','error')),
    total       INTEGER NOT NULL DEFAULT 0,
    saved       INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS job_items (
    job_id     TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    regla      TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pendiente'
               CHECK (status IN ('pendiente','en_curso','completado','ambigua','error')),
    fase       TEXT,
    intento    INTEGER,
    check_id   TEXT,
    n_casos    INTEGER,
    error      TEXT,
    updated_at TEXT,
    PRIMARY KEY (job_id, idx)
);
CREATE INDEX IF NOT EXISTS idx_jobs_revision ON jobs(revision_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = (checks_db.connect(db_path) if db_path is not None
            else checks_db.connect())
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def create(conn: sqlite3.Connection, revision_id: str,
           rules: list[str]) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO jobs (job_id, revision_id, status, total, created_at, "
        "updated_at) VALUES (?,?,?,?,?,?)",
        (job_id, revision_id, "pendiente", len(rules), _now(), _now()))
    conn.executemany(
        "INSERT INTO job_items (job_id, idx, regla, status, updated_at) "
        "VALUES (?,?,?,?,?)",
        [(job_id, i, rule, "pendiente", _now())
         for i, rule in enumerate(rules, start=1)])
    conn.commit()
    return job_id


def set_job_status(conn: sqlite3.Connection, job_id: str, status: str, *,
                   saved: int | None = None, failed: int | None = None,
                   error: str | None = None) -> None:
    if status not in JOB_STATUSES:
        raise ValueError(f"unknown job status: {status!r}")
    sets = ["status=?", "updated_at=?"]
    params: list = [status, _now()]
    if saved is not None:
        sets.insert(1, "saved=?"); params.insert(1, saved)
    if failed is not None:
        sets.insert(1, "failed=?"); params.insert(1, failed)
    if error is not None:
        sets.insert(1, "error=?"); params.insert(1, error)
    params.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=?", params)
    conn.commit()


def set_item(conn: sqlite3.Connection, job_id: str, idx: int, *,
             status: str | None = None, fase: str | None = None,
             intento: int | None = None, check_id: str | None = None,
             n_casos: int | None = None, error: str | None = None) -> None:
    """Patch one rule's row. Only the fields given are touched, so a
    progress update does not erase what an earlier one recorded."""
    if status is not None and status not in ITEM_STATUSES:
        raise ValueError(f"unknown item status: {status!r}")
    fields = {"status": status, "fase": fase, "intento": intento,
              "check_id": check_id, "n_casos": n_casos, "error": error}
    given = {k: v for k, v in fields.items() if v is not None}
    if not given:
        return
    sets = ", ".join(f"{k}=?" for k in given)
    conn.execute(
        f"UPDATE job_items SET {sets}, updated_at=? WHERE job_id=? AND idx=?",
        [*given.values(), _now(), job_id, idx])
    conn.commit()


def get(conn: sqlite3.Connection, job_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM jobs WHERE job_id=?",
                       (job_id,)).fetchone()
    if not row:
        return None
    items = [dict(r) for r in conn.execute(
        "SELECT * FROM job_items WHERE job_id=? ORDER BY idx", (job_id,))]
    job = dict(row)
    job["items"] = items
    job["done"] = sum(1 for i in items if i["status"] in
                      ("completado", "ambigua", "error"))
    return job


def latest_for_revision(conn: sqlite3.Connection,
                        revision_id: str) -> dict | None:
    row = conn.execute(
        "SELECT job_id FROM jobs WHERE revision_id=? "
        "ORDER BY created_at DESC LIMIT 1", (revision_id,)).fetchone()
    return get(conn, row["job_id"]) if row else None
