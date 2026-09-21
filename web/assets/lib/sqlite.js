/* Running a generated control in the browser.
 *
 * The table under review is loaded into SQLite compiled to WebAssembly
 * (sql.js, vendored in assets/vendor). Nothing leaves the machine: the
 * file is read locally and the query runs locally.
 *
 * The query was written by a language model, so read-only is checked, not
 * assumed. Here the blast radius is one in-memory database, but a control
 * that silently dropped the table would still produce nonsense results.
 */

const WASM_DIR = new URL('../vendor/', import.meta.url).href;

let sqlPromise = null;

/** Load sql.js once per page. */
function loadSql() {
  if (!sqlPromise) {
    sqlPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = WASM_DIR + 'sql-wasm.js';
      script.onload = () =>
        window
          .initSqlJs({ locateFile: (file) => WASM_DIR + file })
          .then(resolve, reject);
      script.onerror = () =>
        reject(new Error('No se pudo cargar SQLite (assets/vendor/sql-wasm.js).'));
      document.head.appendChild(script);
    });
  }
  return sqlPromise;
}

const FORBIDDEN = [
  'insert',
  'update',
  'delete',
  'merge',
  'upsert',
  'truncate',
  'drop',
  'alter',
  'create',
  'replace',
  'grant',
  'revoke',
  'commit',
  'rollback',
  'call',
  'exec',
  'execute',
  'attach',
  'detach',
  'pragma',
  'vacuum',
  'copy',
  'load',
  'into',
  'lock',
];

/** Throw unless `sql` is a single SELECT. Strict on purpose: a false
    rejection costs one correction round, a false acceptance runs a
    model-written statement. */
export function assertReadOnly(sql) {
  const withoutComments = String(sql || '').replace(/--[^\n]*|\/\*[\s\S]*?\*\//g, ' ');
  const withoutLiterals = withoutComments.replace(/'([^']|'')*'/g, "''");
  const body = withoutLiterals
    .trim()
    .replace(/;+\s*$/, '')
    .trim();
  if (!body) throw new Error('La consulta está vacía.');
  if (body.includes(';')) throw new Error('Solo se admite UNA sentencia por control.');
  const lowered = body.toLowerCase();
  if (!/^(select|with)\b/.test(lowered)) {
    throw new Error('El control debe ser una consulta SELECT.');
  }
  for (const word of FORBIDDEN) {
    if (new RegExp(`\\b${word}\\b`).test(lowered)) {
      throw new Error(
        `La consulta contiene '${word.toUpperCase()}', que no es de solo lectura.`,
      );
    }
  }
}

/** Point a generated query at the table as it is really named. The model
    writes what the prompt called it ("mylib.contratos"). */
export function normaliseTable(sql, promptTable, realTable) {
  let query = String(sql)
    .trim()
    .replace(/;+\s*$/, '');
  query = query.replace(/^\s*(proc\s+sql\s*;|quit\s*;?)\s*$/gim, '').trim();
  const bare = String(promptTable).split('.').pop();
  const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // Substitute through a token first: replacing straight to `"table"` makes
  // the later passes find the name again inside the quotes they just added,
  // and the query comes out as ""table"".
  const TOKEN = '\u0000T\u0000';
  // …and skip names the model already quoted, or they get quoted twice.
  const unquoted = (body) => new RegExp(`(?<!")${body}(?!")`, 'gi');
  // \b matters: without it, a column named CONTRATOS_ID becomes
  // "contratos"_ID when the table is called contratos.
  query = query.replace(unquoted(`\\b${escape(promptTable)}\\b`), TOKEN);
  query = query.replace(unquoted(`\\b[A-Za-z_]\\w*\\.${escape(bare)}\\b`), TOKEN);
  query = query.replace(unquoted(`\\b${escape(bare)}\\b`), TOKEN);
  return query.split(TOKEN).join(`"${realTable}"`);
}

export const MAX_EXAMPLE_ROWS = 50;
export const MAX_EXAMPLE_COLS = 8;
export const MAX_FETCH_ROWS = 500;

/** A CSV loaded into an in-memory SQLite table, ready to be queried. */
export class Dataset {
  constructor(db, table, headers, nRows) {
    this.db = db;
    this.table = table;
    this.headers = headers;
    this.nRows = nRows;
  }

  static async fromCsv({ headers, rows }, tableName) {
    const SQL = await loadSql();
    const db = new SQL.Database();
    const table =
      String(tableName || 'tabla')
        .split('.')
        .pop()
        .replace(/\W+/g, '_') || 'tabla';
    const columns = headers.map((h) => `"${String(h).replace(/"/g, '""')}"`).join(', ');
    db.run(`CREATE TABLE "${table}" (${columns})`);

    const placeholders = headers.map(() => '?').join(', ');
    const insert = db.prepare(`INSERT INTO "${table}" VALUES (${placeholders})`);
    db.run('BEGIN');
    for (const row of rows) {
      const values = headers.map((_, i) => (row[i] === undefined ? null : row[i]));
      insert.run(values);
    }
    db.run('COMMIT');
    insert.free();
    return new Dataset(db, table, headers, rows.length);
  }

  /** Execute one control. Never throws on a bad query: the message feeds
      the correction loop, exactly as the backend version did. */
  run(sql, promptTable) {
    try {
      assertReadOnly(sql);
    } catch (err) {
      return { ok: false, error: err.message };
    }
    const query = normaliseTable(sql, promptTable || this.table, this.table);
    let stmt;
    try {
      stmt = this.db.prepare(query);
      const columns = [];
      const rows = [];
      while (stmt.step() && rows.length < MAX_FETCH_ROWS) {
        if (!columns.length) columns.push(...stmt.getColumnNames());
        rows.push(stmt.get());
      }
      if (!columns.length) columns.push(...stmt.getColumnNames());
      stmt.free();

      const shown = columns.slice(0, MAX_EXAMPLE_COLS);
      const ejemplos = rows.slice(0, MAX_EXAMPLE_ROWS).map((row) => {
        const item = {};
        shown.forEach((name) => {
          const value = row[columns.indexOf(name)];
          item[name] =
            value === null || value === undefined ? '' : String(value).slice(0, 40);
        });
        return item;
      });
      return { ok: true, columnas: shown, ejemplos, n_casos: rows.length };
    } catch (err) {
      if (stmt) {
        try {
          stmt.free();
        } catch (_) {
          /* already freed */
        }
      }
      return { ok: false, error: `la consulta falla al ejecutarse: ${err.message}` };
    }
  }

  /** Real values per field, so the model compares against values that
      exist instead of inventing them. */
  sampleValues(names, maxFields = 10, maxValues = 8) {
    const known = new Map(this.headers.map((h) => [String(h).toLowerCase(), h]));
    const out = {};
    for (const name of (names || []).slice(0, maxFields)) {
      const column = known.get(String(name).toLowerCase());
      if (!column) continue;
      const result = this.run(
        `SELECT DISTINCT "${column}" FROM "${this.table}" WHERE "${column}" IS NOT NULL`,
        this.table,
      );
      if (!result.ok) continue;
      const values = result.ejemplos
        .map((row) => row[column])
        .filter(Boolean)
        .slice(0, maxValues);
      if (values.length) out[column] = values;
    }
    return out;
  }

  close() {
    try {
      this.db.close();
    } catch (_) {
      /* already closed */
    }
  }
}
