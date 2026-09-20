"""SQLite persistence for revisions — a review of one data table.

A revision is what the app's home screen lists: a name, the description
of the table under review, the uploaded data file, its dictionary, and
the state of the run. It is the unit the generated controls hang off:
every check carries the revision id in its ``project_id`` column, so
"the rules of this revision" is a filter the checks store already knows
how to apply.

Uploaded files live on disk under :data:`FILES_DIR` (one folder per
revision) rather than in the DB — they are read back whole on every
generation, and SQLite blobs would buy nothing.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from training.dq import checks_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FILES_DIR = Path(os.getenv("REGLLM_REVISIONS_DIR",
                           PROJECT_ROOT / "data" / "revisions"))

STATUSES = ("pendiente", "en_ejecucion", "completada", "error")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS revisions (
    revision_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT NOT NULL,
    table_name          TEXT NOT NULL,
    data_filename       TEXT,
    data_rows           INTEGER NOT NULL DEFAULT 0,
    data_columns        INTEGER NOT NULL DEFAULT 0,
    dictionary_filename TEXT,
    dictionary_fields   INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'pendiente'
                        CHECK (status IN ('pendiente','en_ejecucion','completada','error')),
    created_at          TEXT NOT NULL,
    updated_at          TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Same database file as the checks store — one file to back up."""
    conn = (checks_db.connect(db_path) if db_path is not None
            else checks_db.connect())
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def files_dir(revision_id: str) -> Path:
    path = FILES_DIR / revision_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def create(conn: sqlite3.Connection, *, name: str, description: str,
           table_name: str, data_filename: str | None = None,
           data_rows: int = 0, data_columns: int = 0) -> str:
    revision_id = f"rev_{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO revisions (revision_id, name, description, table_name, "
        "data_filename, data_rows, data_columns, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (revision_id, name, description, table_name, data_filename,
         data_rows, data_columns, _now(), _now()))
    conn.commit()
    return revision_id


def update(conn: sqlite3.Connection, revision_id: str, **fields) -> bool:
    """Patch the named columns. Unknown columns are refused loudly rather
    than silently dropped — a typo here would be a state bug."""
    allowed = {"name", "description", "table_name", "data_filename",
               "data_rows", "data_columns", "dictionary_filename",
               "dictionary_fields", "status"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown revision column(s): {sorted(unknown)}")
    if not fields:
        return False
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"unknown revision status: {fields['status']!r}")
    sets = ", ".join(f"{k}=?" for k in fields)
    cur = conn.execute(
        f"UPDATE revisions SET {sets}, updated_at=? WHERE revision_id=?",
        [*fields.values(), _now(), revision_id])
    conn.commit()
    return cur.rowcount > 0


def get(conn: sqlite3.Connection, revision_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM revisions WHERE revision_id=?",
                       (revision_id,)).fetchone()
    return dict(row) if row else None


def list_all(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM revisions ORDER BY created_at DESC")]


def delete(conn: sqlite3.Connection, revision_id: str) -> bool:
    """Drop the revision, its controls and its uploaded files together —
    a revision whose files outlive it is just disk nobody can reach."""
    cur = conn.execute("DELETE FROM revisions WHERE revision_id=?",
                       (revision_id,))
    conn.execute("DELETE FROM checks WHERE project_id=?", (revision_id,))
    conn.commit()
    shutil.rmtree(FILES_DIR / revision_id, ignore_errors=True)
    return cur.rowcount > 0
