"""Where a generated control actually runs.

The agent derives a query; something has to execute it and say which rows
it flags. Until now that something was always the uploaded file, parsed
into an in-memory SQLite table. That is one implementation of one idea,
and it is the wrong one when the table under review lives in the bank's
own database: nobody is going to export a production table to Excel to
review it, and copying it to us is the part that does not get approved.

So execution sits behind :class:`QueryExecutor`:

* :class:`UploadedTableExecutor` — the uploaded .csv/.xlsx, as today.
* :class:`DatabaseExecutor` — any PEP 249 (DB-API 2.0) connection, which
  is what cx_Oracle, pyodbc, psycopg2 and snowflake-connector all expose.
  The query runs where the data already is; only the counts and a small
  sample of rows come back.

Both answer the same three questions the agent loop asks, so the loop
does not know or care which one it got.

**Read-only is enforced here, not assumed.** The query being executed was
written by a language model, and on the database side it may be pointed
at a real schema. :func:`assert_read_only` rejects anything that is not a
single SELECT before the connection ever sees it. That is a second line
of defence, not the first: the credentials handed to this service must be
read-only in the first place.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

from api.routers import dqc_react as react

__all__ = ["QueryExecutor", "UploadedTableExecutor", "DatabaseExecutor",
           "assert_read_only", "NotReadOnly"]

MAX_EXAMPLE_ROWS = react.MAX_EXAMPLE_ROWS
MAX_EXAMPLE_COLS = react.MAX_EXAMPLE_COLS
MAX_FETCH_ROWS = react.MAX_FETCH_ROWS
MAX_GROUNDING_FIELDS = react.MAX_GROUNDING_FIELDS
MAX_GROUNDING_VALUES = react.MAX_GROUNDING_VALUES


class NotReadOnly(ValueError):
    """The query does something other than read."""


# Statements that write, change or reveal more than the control needs.
# Matched as whole words, outside string literals.
_FORBIDDEN = (
    "insert", "update", "delete", "merge", "upsert", "truncate", "drop",
    "alter", "create", "replace", "grant", "revoke", "commit", "rollback",
    "call", "exec", "execute", "attach", "detach", "pragma", "vacuum",
    "copy", "load", "into", "lock",
)
_STRING_LITERAL = re.compile(r"'([^']|'')*'")
_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)


def assert_read_only(sql: str) -> None:
    """Raise :class:`NotReadOnly` unless ``sql`` is a single SELECT.

    Deliberately strict: one statement, starting with SELECT or WITH, no
    writing keyword anywhere outside a string literal. A false rejection
    costs the agent one correction round; a false acceptance runs a
    model-written statement against the bank's database.
    """
    stripped = _COMMENT.sub(" ", sql)
    stripped = _STRING_LITERAL.sub("''", stripped)
    body = stripped.strip().rstrip(";").strip()
    if not body:
        raise NotReadOnly("la consulta está vacía")
    if ";" in body:
        raise NotReadOnly("solo se admite UNA sentencia por control")
    lowered = body.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise NotReadOnly("el control debe ser una consulta SELECT")
    for word in _FORBIDDEN:
        if re.search(rf"\b{word}\b", lowered):
            raise NotReadOnly(f"la consulta contiene '{word.upper()}', que "
                              f"no es de solo lectura")


@runtime_checkable
class QueryExecutor(Protocol):
    """What the agent loop needs from wherever the data lives."""

    table: str
    headers: list[str]
    n_rows: int

    def run(self, sql: str) -> dict:
        """Execute one control. Returns
        ``{ok, error?, columnas, ejemplos, n_casos, casos}`` — never
        raises on a bad query: the error text feeds the correction loop.
        """

    def sample_values(self, campos: list[str]) -> dict[str, list[str]]:
        """Real values per field, to ground the generation prompt."""

    def metrics(self, casos: set, prev_id: str | None) -> dict | None:
        """Precision/recall against historical labels, when they exist."""


class UploadedTableExecutor:
    """The uploaded .csv/.xlsx, loaded into in-memory SQLite.

    Thin by design: the behaviour has been exercised for a while inside
    ``dqc_react``, and this only gives it the shape the rest of the code
    now expects.
    """

    def __init__(self, cases: react.CasesContext,
                 prompt_table: str | None = None):
        self.cases = cases
        self.table = cases.table
        # what the generation prompt called the table ("mylib.contratos"),
        # which is what the model writes and what has to be rewritten to
        # the real name on the way in
        self.prompt_table = prompt_table or cases.table
        self.headers = cases.headers
        self.n_rows = cases.n_rows

    def run(self, sql: str) -> dict:
        try:
            assert_read_only(sql)
        except NotReadOnly as exc:
            return {"ok": False, "error": str(exc)}
        return react.run_query(self.cases, sql, self.prompt_table)

    def sample_values(self, campos: list[str]) -> dict[str, list[str]]:
        return react.sample_values(self.cases, campos)

    def metrics(self, casos: set, prev_id: str | None) -> dict | None:
        return react.metrics(self.cases, casos, prev_id)


class DatabaseExecutor:
    """A table that already lives in a database, reached over DB-API 2.0.

    Works with any PEP 249 connection — ``cx_Oracle``, ``pyodbc``,
    ``psycopg2``, ``snowflake-connector-python``, and ``sqlite3``, which
    is how it is tested. The driver is the caller's problem; this class
    only promises to read.

    Two differences from the uploaded-file executor, both inherent rather
    than missing work:

    * ``n_casos`` is how many rows the query returned, capped at
      :data:`MAX_FETCH_ROWS`. There is no injected ``_CASO_`` row id to
      count by, so a control whose query returns one row per violation is
      counted exactly and one that aggregates is not.
    * ``metrics`` returns ``None`` unless the table carries a historical
      label column (``label_column``): precision and recall are measured
      against past flags, and a production table rarely has them.
    """

    def __init__(self, connection: Any, table: str, *,
                 schema: str | None = None,
                 prompt_table: str | None = None,
                 label_column: str | None = None,
                 quote: str = '"'):
        self.connection = connection
        self.table = table
        self.schema = schema
        # the name the generation prompt used, rewritten to the real
        # schema-qualified one before the database sees the query
        self.prompt_table = prompt_table or table
        self.label_column = label_column
        self._quote = quote
        self.headers = self._read_headers()
        self.n_rows = self._count_rows()

    # ── identity ────────────────────────────────────────────────────────

    @property
    def qualified(self) -> str:
        name = f"{self._quote}{self.table}{self._quote}"
        if self.schema:
            name = f"{self._quote}{self.schema}{self._quote}.{name}"
        return name

    def _cursor(self, sql: str, params: tuple = ()):
        cur = self.connection.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        return cur

    def _read_headers(self) -> list[str]:
        cur = self._cursor(f"SELECT * FROM {self.qualified} WHERE 1=0")
        try:
            return [d[0] for d in cur.description or []]
        finally:
            cur.close()

    def _count_rows(self) -> int:
        cur = self._cursor(f"SELECT COUNT(*) FROM {self.qualified}")
        try:
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.close()

    # ── QueryExecutor ───────────────────────────────────────────────────

    def run(self, sql: str) -> dict:
        try:
            assert_read_only(sql)
        except NotReadOnly as exc:
            return {"ok": False, "error": str(exc)}

        query = react.normalise_table_reference(sql, self.prompt_table,
                                                self.qualified,
                                                bare=self.table)
        try:
            cur = self._cursor(query)
            rows = cur.fetchmany(MAX_FETCH_ROWS)
            columns = [d[0] for d in cur.description or []]
            cur.close()
        except Exception as exc:  # noqa: BLE001 — feeds the correction loop
            return {"ok": False,
                    "error": f"la consulta falla al ejecutarse sobre "
                             f"{self.table}: {exc}"}

        shown = columns[:MAX_EXAMPLE_COLS]
        ejemplos = [
            {c: ("" if row[columns.index(c)] is None
                 else str(row[columns.index(c)])[:40]) for c in shown}
            for row in rows[:MAX_EXAMPLE_ROWS]
        ]
        casos: set = set()
        if self.label_column and self.label_column in columns:
            idx = columns.index(self.label_column)
            casos = {row[idx] for row in rows if row[idx] is not None}
        return {"ok": True, "columnas": shown, "ejemplos": ejemplos,
                "n_casos": len(rows), "casos": casos}

    def sample_values(self, campos: list[str]) -> dict[str, list[str]]:
        known = {h.lower(): h for h in self.headers}
        out: dict[str, list[str]] = {}
        for name in campos[:MAX_GROUNDING_FIELDS]:
            col = known.get(str(name).lower())
            if not col:
                continue
            q = self._quote
            try:
                cur = self._cursor(
                    f"SELECT DISTINCT {q}{col}{q} FROM {self.qualified} "
                    f"WHERE {q}{col}{q} IS NOT NULL")
                rows = cur.fetchmany(MAX_GROUNDING_VALUES)
                cur.close()
            except Exception:  # noqa: BLE001 — grounding is best-effort
                continue
            values = [str(r[0])[:30] for r in rows
                      if r[0] is not None and str(r[0]).strip()]
            if values:
                out[col] = values
        return out

    def metrics(self, casos: set, prev_id: str | None) -> dict | None:
        # Historical precision/recall needs past flags stored next to the
        # rows. Without a label column there is nothing to compare against,
        # and inventing a number here would be worse than saying nothing.
        return None
