/* Reading a CSV in the browser.
 *
 * No dependency: a CSV is quoted fields separated by a delimiter, and the
 * only parts that need care are quotes containing the delimiter and the
 * Spanish export that uses ';' with a decimal comma.
 *
 * Numbers become numbers. Without that, SQLite compares text against a
 * number — and in SQLite every integer sorts before every string, so
 * `EDAD > 130` would match every row of the file.
 */

const DELIMITERS = [',', ';', '\t', '|'];

/** Guess the delimiter from the header line: the one that appears most,
    outside quotes. */
function sniffDelimiter(text) {
  const header = text.slice(0, text.indexOf('\n') + 1 || 2000);
  let best = ',';
  let bestCount = 0;
  for (const d of DELIMITERS) {
    const count = header.split(d).length - 1;
    if (count > bestCount) {
      best = d;
      bestCount = count;
    }
  }
  return best;
}

/** Split one line honouring double quotes ("" is an escaped quote). */
function splitLine(line, delimiter) {
  const out = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          quoted = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === delimiter) {
      out.push(field);
      field = '';
    } else {
      field += ch;
    }
  }
  out.push(field);
  return out;
}

const INT_RE = /^[+-]?(0|[1-9]\d*)$/;
const DEC_RE = /^[+-]?(0|[1-9]\d*)\.\d+$/;
const DEC_COMMA_RE = /^[+-]?(0|[1-9]\d*),\d+$/;

/** Numbers become numbers; everything else stays text. A leading zero
    keeps a value textual on purpose: `007` is an identifier, not 7. */
function coerce(text, decimalComma) {
  if (text === '') return null;
  if (INT_RE.test(text)) return Number(text);
  if (DEC_RE.test(text)) return Number(text);
  if (decimalComma && DEC_COMMA_RE.test(text)) return Number(text.replace(',', '.'));
  return text;
}

/** Parse CSV text into {headers, rows}. Blank lines are dropped; the first
    non-empty line is the header. */
export function parseCsv(text) {
  const clean = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n');
  const delimiter = sniffDelimiter(clean);
  // "1,5" can only be a decimal when the comma is not separating columns
  const decimalComma = delimiter !== ',';

  const lines = clean.split('\n').filter((l) => l.trim() !== '');
  if (!lines.length) throw new Error('El fichero está vacío.');

  const headers = splitLine(lines[0], delimiter).map((h) => h.trim());
  if (!headers.length || headers.every((h) => h === '')) {
    throw new Error('El fichero no tiene cabeceras.');
  }

  const rows = lines
    .slice(1)
    .map((line) =>
      splitLine(line, delimiter).map((cell) => coerce(cell.trim(), decimalComma)),
    );
  return { headers, rows, delimiter };
}

/** Read a File as text, tolerating the encodings Excel produces. */
export async function readFileText(file) {
  const buffer = await file.arrayBuffer();
  const utf8 = new TextDecoder('utf-8', { fatal: false }).decode(buffer);
  // U+FFFD means the bytes were not UTF-8 — the other common export here
  // is Windows-1252
  if (utf8.includes('�')) {
    try {
      return new TextDecoder('windows-1252').decode(buffer);
    } catch (_) {
      return utf8;
    }
  }
  return utf8;
}

/** A field dictionary: one row per column of the table under review.
    Header names are matched loosely because every bank writes them
    differently. */
const FIELD_HINTS = [
  'campo',
  'field',
  'columna',
  'column',
  'nombre',
  'name',
  'variable',
];
const TYPE_HINTS = ['tipo', 'type', 'formato', 'datatype'];
const DESC_HINTS = [
  'descripcion',
  'descripción',
  'description',
  'definicion',
  'definición',
  'desc',
];

function normalise(text) {
  return String(text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim();
}

function findColumn(headers, hints) {
  const index = headers.findIndex((h) => hints.some((hint) => normalise(h) === hint));
  if (index !== -1) return index;
  return headers.findIndex((h) => hints.some((hint) => normalise(h).includes(hint)));
}

export function parseDictionary(text) {
  const { headers, rows } = parseCsv(text);
  const nameIdx = findColumn(headers, FIELD_HINTS);
  if (nameIdx === -1) {
    throw new Error(
      'No se reconoció la columna con el nombre del campo. Se esperan ' +
        'cabeceras tipo Campo/Field/Columna.',
    );
  }
  const typeIdx = findColumn(headers, TYPE_HINTS);
  const descIdx = findColumn(headers, DESC_HINTS);

  const fields = [];
  for (const row of rows) {
    const nombre = String(row[nameIdx] ?? '').trim();
    if (!nombre) continue;
    fields.push({
      nombre,
      tipo: typeIdx === -1 ? '' : String(row[typeIdx] ?? '').trim(),
      descripcion: descIdx === -1 ? '' : String(row[descIdx] ?? '').trim(),
    });
  }
  if (!fields.length) throw new Error('El diccionario no tiene ningún campo.');
  return fields;
}
