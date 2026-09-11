/* DQC Studio — single-page app.
   Modernist design (see assets/styles.css + app.css) implementing the
   Proyectos → Generar → Revisar flow from the design prototype, wired to the
   DQC FastAPI backend. With ?demo=1 (or when served from GitHub Pages) it
   replays the whole workflow from a client-side seed instead of calling the
   API, so the UI can be shown with no model, no API and no AWS. */

/* ── environment ─────────────────────────────────────────────────────────── */
const API = (window.DQC_API_BASE ?? new URLSearchParams(location.search).get('api') ?? '/api').replace(/\/$/, '');
const DEMO = new URLSearchParams(location.search).has('demo') ||
             (typeof location !== 'undefined' && location.hostname.endsWith('github.io'));
const LS_PROJECTS = 'dqc_studio_projects';

/* ── demo seed (mirrors the design prototype) ────────────────────────────── */
const DEMO_SEED = [
  { id: 'DQC_001', name: 'Fecha de fin posterior a la de inicio', variable: 'FEC_FIN_CICLO',
    desc: 'Ningún ciclo de recuperación puede cerrarse antes de haber empezado. Se marcan las filas cuya fecha de fin es anterior a la de inicio.',
    sev: 'ALTA', status: 'pending', casos: 14,
    sql: "SELECT contrato, ciclo, FEC_INI_CICLO, FEC_FIN_CICLO\n  FROM mylib.ciclos_recuperacion\n WHERE FEC_FIN_CICLO IS NOT NULL\n   AND FEC_FIN_CICLO < FEC_INI_CICLO;",
    hint: 'Estas 14 filas se marcan porque cumplen la condición de error: FEC_FIN_CICLO < FEC_INI_CICLO.',
    trace: [
      { k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. Campos localizados: FEC_INI_CICLO (fecha, obligatorio) y FEC_FIN_CICLO (fecha, opcional).' },
      { k: 'ok', label: 'Consulta construida', detail: 'Comparación directa de fechas, excluyendo ciclos abiertos (fin nulo).' },
      { k: 'ok', label: 'Ejecutada contra los casos de prueba', detail: '14 casos detectados de 14 esperados. Precisión 100 % · Cobertura 100 %.' },
      { k: 'ok', label: 'Revisión semántica', detail: 'La consulta responde a la regla escrita, sin condiciones añadidas.' }
    ],
    cols: ['contrato', 'ciclo', 'fec_ini_ciclo', 'fec_fin_ciclo'],
    rows: [['0041872', '3', '2026-02-14', '2026-01-30'], ['0052310', '1', '2026-03-02', '2026-02-27'], ['0061044', '2', '2026-01-09', '2025-12-31']],
    bcbs239: 'P13 — Reconciliation',
    explicacion: { explicacion: 'Las fechas de fin anteriores a las de inicio sugieren un error de captura o la inversión de los dos campos al cargar la cartera.', factor_comun: 'Datos de contratos reprogramados o con errores de grabación en el campo de fecha.', posible_causa: 'captura', recomendacion: 'Revisar la carga del campo FEC_FIN_CICLO en los contratos afectados.' } },
  { id: 'DQC_002', name: 'Importe pendiente nunca negativo', variable: 'IMP_PENDIENTE',
    desc: 'El importe pendiente de un ciclo es un saldo: cero o positivo. Un valor negativo indica un abono mal imputado.',
    sev: 'ALTA', status: 'pending', casos: 6,
    sql: "SELECT contrato, ciclo, IMP_PENDIENTE\n  FROM mylib.ciclos_recuperacion\n WHERE IMP_PENDIENTE < 0;",
    hint: 'Estas 6 filas se marcan porque cumplen la condición de error: IMP_PENDIENTE < 0.',
    trace: [
      { k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. IMP_PENDIENTE (numérico, 15,2) con dominio documentado «≥ 0».' },
      { k: 'ok', label: 'Consulta construida', detail: 'Filtro de signo sobre el importe.' },
      { k: 'warn', label: 'Ejecutada contra los casos de prueba', detail: 'Primer intento: 0 casos. Se detectó que el campo llega como texto en el Excel; se repitió con conversión numérica.' },
      { k: 'ok', label: 'Segundo intento', detail: '6 casos detectados de 6 esperados. Precisión 100 % · Cobertura 100 %.' }
    ],
    cols: ['contrato', 'ciclo', 'imp_pendiente'],
    rows: [['0033901', '2', '-125,40'], ['0048227', '1', '-3.410,00'], ['0071650', '4', '-18,75']],
    bcbs239: 'P3 — Accuracy and integrity',
    explicacion: { explicacion: 'Valores negativos en un saldo pendiente indican abonos o reversiones mal imputadas al ciclo de recuperación.', factor_comun: 'Importes con signo invertido o abonos no segregados.', posible_causa: 'conversión', recomendacion: 'Comprobar la imputación de abonos y el redondeo de importes negativos.' } },
  { id: 'DQC_003', name: 'Código de gestor existente en el maestro', variable: 'COD_GESTOR',
    desc: 'Todo ciclo asignado debe apuntar a un gestor vivo en el maestro de gestores. Se marcan los códigos huérfanos.',
    sev: 'MEDIA', status: 'pending', casos: 23,
    sql: "SELECT c.contrato, c.ciclo, c.COD_GESTOR\n  FROM mylib.ciclos_recuperacion c\n  LEFT JOIN mylib.maestro_gestores g\n    ON g.COD_GESTOR = c.COD_GESTOR\n WHERE c.COD_GESTOR IS NOT NULL\n   AND g.COD_GESTOR IS NULL;",
    hint: 'Estas 23 filas se marcan porque su COD_GESTOR no aparece en el maestro de gestores.',
    trace: [
      { k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. COD_GESTOR está marcado como clave externa hacia mylib.maestro_gestores.' },
      { k: 'ok', label: 'Consulta construida', detail: 'LEFT JOIN contra el maestro, quedándose con lo no emparejado.' },
      { k: 'ok', label: 'Ejecutada contra los casos de prueba', detail: '23 casos detectados de 25 esperados. Precisión 100 % · Cobertura 92 %.' },
      { k: 'warn', label: 'Revisión semántica', detail: 'Los 2 casos no detectados son gestores dados de baja este mes: el maestro los conserva. Puede requerir un filtro por fecha de baja.' }
    ],
    cols: ['contrato', 'ciclo', 'cod_gestor'],
    rows: [['0019334', '1', 'G-8841'], ['0027781', '2', 'G-9002'], ['0055120', '1', 'G-8841']],
    bcbs239: 'P13 — Reconciliation',
    explicacion: { explicacion: 'Ciclos cuyos gestores no existen en el maestro: integridad referencial rota entre la tabla de ciclos y el maestro de gestores.', factor_comun: 'Códigos de gestor dados de baja o ausentes del maestro.', posible_causa: 'cambio de regla', recomendacion: 'Confirmar si son bajas vigentes y filtrar por fecha de baja antes de reportar.' } },
  { id: 'DQC_004', name: 'Estado del ciclo dentro del dominio permitido', variable: 'EST_CICLO',
    desc: 'El estado solo puede tomar los cinco valores del catálogo funcional. Cualquier otro valor rompe el cuadro de mando.',
    sev: 'MEDIA', status: 'validated', casos: 2,
    sql: "SELECT contrato, ciclo, EST_CICLO\n  FROM mylib.ciclos_recuperacion\n WHERE EST_CICLO NOT IN ('ABIERTO','GESTION','ACUERDO','CERRADO','FALLIDO');",
    hint: 'Estas 2 filas se marcan porque su estado no está en el catálogo funcional.',
    trace: [
      { k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. Dominio de cinco valores tomado del funcional (apartado 4.2) y confirmado en el diccionario.' },
      { k: 'ok', label: 'Consulta construida', detail: 'Comprobación de pertenencia al catálogo.' },
      { k: 'ok', label: 'Ejecutada contra los casos de prueba', detail: '2 casos detectados de 2 esperados. Precisión 100 % · Cobertura 100 %.' }
    ],
    cols: ['contrato', 'ciclo', 'est_ciclo'],
    rows: [['0038812', '3', 'PEND_REV'], ['0064009', '1', 'gestion ']],
    bcbs239: 'P3 — Accuracy and integrity',
    explicacion: { explicacion: 'Estados fuera del catálogo funcional con variantes de mayúsculas o espacios, y valores de catálogo antiguos no migrados.', factor_comun: 'Códigos de estado con formato o mayúsculas inconsistentes.', posible_causa: 'captura', recomendacion: 'Normalizar EST_CICLO y depurar el catálogo de estados vigente.' } },
  { id: 'DQC_005', name: 'Un solo ciclo abierto por contrato', variable: 'NUM_CICLO',
    desc: 'Un contrato no puede tener dos ciclos de recuperación abiertos a la vez. Se marcan los contratos con más de uno.',
    sev: 'ALTA', status: 'pending', casos: 9,
    sql: "SELECT contrato, COUNT(*) AS abiertos\n  FROM mylib.ciclos_recuperacion\n WHERE EST_CICLO IN ('ABIERTO','GESTION')\n GROUP BY contrato\nHAVING COUNT(*) > 1;",
    hint: 'Estos 9 contratos se marcan porque acumulan más de un ciclo en estado abierto o en gestión.',
    trace: [
      { k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. La unicidad por contrato está descrita en el funcional; los estados abiertos se toman del catálogo.' },
      { k: 'ok', label: 'Consulta construida', detail: 'Agregación por contrato con filtro sobre el recuento.' },
      { k: 'ok', label: 'Ejecutada contra los casos de prueba', detail: '9 casos detectados de 9 esperados. Precisión 100 % · Cobertura 100 %.' },
      { k: 'ok', label: 'Revisión semántica', detail: 'Coincide con la lógica del programa SAS revisado (ciclos_recuperacion.sas, líneas 210-244).' }
    ],
    cols: ['contrato', 'abiertos'],
    rows: [['0022145', '2'], ['0040018', '3'], ['0059930', '2']],
    bcbs239: 'P6 — Adaptability',
    explicacion: { explicacion: 'Contratos con más de un ciclo en estado abierto o en gestión: se incumple la cardinalidad de un único ciclo activo por contrato.', factor_comun: 'Contratos con ciclos duplicados o solapados.', posible_causa: 'reproceso', recomendacion: 'Revisar los ciclos duplicados y su estado en el programa SAS de altas.' } },
  { id: 'DQC_006', name: 'Fecha de alta no futura', variable: 'FEC_ALTA',
    desc: 'La fecha de alta del ciclo no puede ser posterior a la fecha de proceso.',
    sev: 'BAJA', status: 'rejected', casos: 0,
    sql: "SELECT contrato, ciclo, FEC_ALTA\n  FROM mylib.ciclos_recuperacion\n WHERE FEC_ALTA > CURRENT_DATE;",
    hint: 'Sin casos en el Excel de pruebas.',
    trace: [
      { k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. FEC_ALTA (fecha, obligatorio).' },
      { k: 'ok', label: 'Consulta construida', detail: 'Comparación con la fecha actual del sistema.' },
      { k: 'warn', label: 'Ejecutada contra los casos de prueba', detail: '0 casos detectados de 4 esperados: la comparación debería usar la fecha de proceso del cierre, no CURRENT_DATE.' }
    ],
    cols: ['contrato', 'ciclo', 'fec_alta'],
    rows: [],
    bcbs239: 'P5 — Timeliness',
    explicacion: null }
];

const DEMO_MARKS = { ok: { mark: '✓', rule: '#201e1d' }, warn: { mark: '!', rule: '#dd2b0f' }, bad: { mark: '✗', rule: '#ec3013' } };
const DEMO_STATUS = {
  pending: { estado: 'Pendiente', bg: '#d7d3d3', fg: '#201e1d' },
  validated: { estado: 'Validado', bg: '#201e1d', fg: '#ffffff' },
  rejected: { estado: 'Rechazado', bg: '#ec3013', fg: '#ffffff' }
};
const DEMO_SEV = {
  ALTA: { bg: '#ec3013', fg: '#ffffff' }, MEDIA: { bg: '#fff2ef', fg: '#7c1405' }, BAJA: { bg: '#f8f4f4', fg: '#444141' }
};
const DEMO_PHASES = [
  { fase: 'Buscando los campos en el diccionario…', k: 'ok', label: '¿Hay información suficiente en el diccionario?', detail: 'Sí. Campos localizados y tipos inferidos desde la hoja «Campos».' },
  { fase: 'Construyendo la consulta…', k: 'ok', label: 'Consulta construida', detail: 'Condición de error derivada de la regla y del funcional adjunto.' },
  { fase: 'Probándola contra los casos…', k: 'ok', label: 'Ejecutada contra los casos de prueba', detail: 'Casos detectados con precisión y cobertura del 100 %.' }
];
const DEMO_DEFAULT_RULES = 'La fecha de fin del ciclo no puede ser anterior a la fecha de inicio\nEl importe pendiente no puede ser negativo\nEl código de gestor debe existir en el maestro de gestores';

/* ── state ───────────────────────────────────────────────────────────────── */
const state = {
  screen: 'projects',          // projects | wizard | project
  wizardStep: 1,
  projectTab: 'resumen',       // resumen | generar | revisar
  projectName: '',
  projectTable: '',
  draftName: 'Ciclos de recuperación — cartera 2026',
  draftTable: 'mylib.ciclos_recuperacion',
  draftFiles: [],              // files captured at project creation (metadata)
  queue: [],                   // 1b — rules added one by one, with live recognised fields
  queueInput: '',
  rules: DEMO_DEFAULT_RULES,
  checks: [],                  // active project's checks
  generating: false,
  genDone: false,
  plan: [],
  reviewIdx: 0,
  dictionaryFile: null,
  casesFile: null,
  error: '',
  banner: false,
  showTrace: true,
  showFiles: false,            // hidden project-files viewer in the header
  currentCases: null,          // latest cases payload for the check in review
  currentCasesForId: null,     // guard so we don't re-fetch on every render
  apiAvailable: null,
};

/* ── projects registry (localStorage) ────────────────────────────────────── */
function loadProjects() {
  try { return JSON.parse(localStorage.getItem(LS_PROJECTS) || '[]'); }
  catch { return []; }
}
function saveProjects(p) { localStorage.setItem(LS_PROJECTS, JSON.stringify(p)); }
let projects = loadProjects();
if (projects.length === 0) {
  projects = [
    { id: 'p1', name: 'Ciclos de recuperación — cartera 2026', table: 'mylib.ciclos_recuperacion', dict: 'diccionario_campos_2026.xlsx', sources: 'funcional_ciclos.docx · ciclos_recuperacion.sas', files: [
      { name: 'diccionario_campos_2026.xlsx', size: 128000, type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', addedAt: '2026-01-10' },
      { name: 'funcional_ciclos.docx', size: 412000, type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', addedAt: '2026-01-10' },
      { name: 'ciclos_recuperacion.sas', size: 98000, type: 'text/plain', addedAt: '2026-01-10' },
      { name: 'casos_prueba.xlsx', size: 88000, type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', addedAt: '2026-01-10' },
    ] },
    { id: 'p2', name: 'Provisiones IFRS 9 — cierre trimestral', table: 'mylib.provisiones_ifrs9', dict: 'diccionario_provisiones.xlsx', sources: 'funcional_provisiones.docx', files: [
      { name: 'diccionario_provisiones.xlsx', size: 76000, type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', addedAt: '2026-02-15' },
      { name: 'funcional_provisiones.docx', size: 512000, type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', addedAt: '2026-02-15' },
    ] },
  ];
  saveProjects(projects);
}
let currentProjectId = null;

/* ── dom helpers ─────────────────────────────────────────────────────────── */
const $ = (s, el = document) => el.querySelector(s);
const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstChild; };
/* ── decision trace ───────────────────────────────────────────────────────
   The backend streams steps shaped {paso, pregunta, resultado, detalle,
   intento, accion, estado}; the demo seed uses {k, label, detail}. Normalise
   both to {mark, rule, label, detail, intento} so "Cómo se decidió" renders
   the real run and not a column of identical ticks. */
const TRACE_MARKS = {
  ok:   { mark: '✓', rule: '#201e1d' },
  no:   { mark: '✗', rule: '#ec3013' },
  warn: { mark: '!', rule: '#dd2b0f' },
  step: { mark: '›', rule: '#6b6664' },
};
const TRACE_STEP_LABEL = {
  suficiencia: '¿Información suficiente?',
  generacion: 'Generar consulta SAS',
  validacion: '¿Consulta válida?',
  juicio: '¿El juez la aprueba?',
  resultado: 'Resultado',
};
const TRACE_OUTCOME = {
  completado: { kind: 'ok', label: 'Control generado' },
  ambigua: { kind: 'warn', label: 'Regla ambigua — no se generó control' },
  error: { kind: 'no', label: 'Sin resultado tras los reintentos' },
};

function normaliseTrace(raw) {
  return (raw || []).map((t) => {
    // demo shape
    if (t.k || (t.label !== undefined && t.paso === undefined)) {
      const m = TRACE_MARKS[t.k === 'bad' ? 'no' : t.k === 'warn' ? 'warn' : 'ok'] || TRACE_MARKS.ok;
      return { mark: m.mark, rule: m.rule, label: t.label || '', detail: t.detail || '', intento: t.intento };
    }
    // backend shape
    let kind = 'step';
    if (t.resultado === 'si') kind = 'ok';
    else if (t.resultado === 'no') kind = 'no';
    let label = t.pregunta || t.accion || TRACE_STEP_LABEL[t.paso] || t.paso || '';
    if (t.paso === 'resultado') {
      const o = TRACE_OUTCOME[t.estado] || { kind: 'step', label: 'Resultado' };
      kind = o.kind; label = o.label;
    }
    if (t.resultado === 'si') label += ' → sí';
    else if (t.resultado === 'no') label += ' → no';
    let detail = t.detalle || '';
    if (t.paso === 'resultado' && t.estado === 'completado' && t.n_casos != null) {
      detail = detail || `${t.n_casos} caso(s) detectado(s)`;
    }
    const m = TRACE_MARKS[kind];
    return { mark: m.mark, rule: m.rule, label, detail, intento: t.intento };
  });
}

/* Group the flat step list into the attempt branches it actually describes:
   sufficiency, then one node per generate→validate→judge retry, then the
   outcome. That is the decision tree, not a flat log. */
function traceTree(steps) {
  const branches = [];
  let current = null;
  for (const st of steps) {
    if (st.intento != null) {
      if (!current || current.intento !== st.intento) {
        current = { intento: st.intento, steps: [] };
        branches.push({ type: 'attempt', ...current });
      }
      current.steps.push(st);
    } else {
      current = null;
      branches.push({ type: 'step', step: st });
    }
  }
  return branches;
}

function renderTraceTree(raw) {
  const branches = traceTree(normaliseTrace(raw));
  if (!branches.length) return '';
  const li = (st) => `<li class="studio-trace-item" style="--trace-rule:${st.rule};">`
    + `<span class="studio-trace-mark" style="color:${st.rule};">${st.mark}</span>`
    + `<span style="min-width:0;"><span class="studio-trace-label">${esc(st.label)}</span>`
    + (st.detail ? `<span class="studio-trace-detail">${esc(st.detail)}</span>` : '')
    + `</span></li>`;
  return `<ol class="studio-trace">${branches.map((b) => b.type === 'step' ? li(b.step) : `
      <li class="studio-trace-branch">
        <span class="studio-trace-branch-head">Intento ${b.intento}</span>
        <ol class="studio-trace studio-trace-nested">${b.steps.map(li).join('')}</ol>
      </li>`).join('')}</ol>`;
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtSize = (b) => { if (b == null) return ''; const n = Number(b); if (n < 1024) return n + ' B'; if (n < 1048576) return (n / 1024).toFixed(0) + ' KB'; return (n / 1048576).toFixed(1) + ' MB'; };
const fileIcon = (t) => { const s = String(t || '').toLowerCase(); if (s.includes('spreadsheet') || s.includes('xls') || s.includes('sheet')) return 'XLSX'; if (s.includes('word') || s.includes('doc')) return 'DOC'; if (s.includes('text') || s.includes('csv') || s.includes('plain')) return 'TXT'; if (s.includes('sas')) return 'SAS'; return 'FILE'; };

/* ── api helpers ─────────────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || JSON.stringify(j); } catch {}
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('json') ? res.json() : res.text();
}

function form(fields) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    if (v === null || v === undefined || v === '') continue;
    fd.append(k, v);
  }
  return fd;
}

/* ── check helpers ───────────────────────────────────────────────────────── */
function counts() {
  return {
    validated: state.checks.filter((c) => c.status === 'validated').length,
    rejected: state.checks.filter((c) => c.status === 'rejected').length,
    pending: state.checks.filter((c) => c.status === 'pending').length,
    total: state.checks.length,
  };
}
function pendingList() { return state.checks.filter((c) => c.status === 'pending'); }
function current() {
  const p = pendingList();
  return p.length ? p[Math.min(state.reviewIdx, p.length - 1)] : null;
}
function buildCentral() {
  const done = state.checks.filter((c) => c.status === 'validated');
  const name = state.projectName || 'Ciclos de recuperación — cartera 2026';
  const table = state.projectTable || 'mylib.ciclos_recuperacion';
  const head = '-- Consulta centralizada de calidad de datos\n'
    + '-- Proyecto: ' + name + '\n-- Tabla objetivo: ' + table + '\n'
    + '-- Controles validados: ' + done.length + '\n-- Generada: ' + new Date().toLocaleString('es-ES') + '\n\n';
  if (!done.length) return head + '-- Todavía no hay controles validados. Valida al menos uno en la pantalla «Revisar».';
  const cte = done.map((c) => '  ' + c.id.toLowerCase() + ' AS (\n'
    + c.sql.replace(/;\s*$/, '').split('\n').map((l) => '    ' + l.trim()).join('\n') + '\n  )').join(',\n');
  const union = done.map((c) => "  SELECT '" + c.id + "' AS control_id,\n"
    + "         '" + c.name.replace(/'/g, "''") + "' AS control,\n"
    + "         '" + c.variable + "' AS campo,\n"
    + "         '" + c.sev + "' AS severidad,\n"
    + '         COUNT(*) AS incidencias\n'
    + '    FROM ' + c.id.toLowerCase()).join('\n  UNION ALL\n');
  return head + 'WITH\n' + cte + '\n'
    + 'SELECT control_id, control, campo, severidad, incidencias\n  FROM (\n'
    + union + '\n  ) resumen_dqc\n ORDER BY incidencias DESC, severidad;\n';
}

/* Validated controls rendered in the same queued-row style as Generar 1b. */
function centralQueueRows() {
  const done = state.checks.filter((c) => c.status === 'validated');
  return done.map((ch) => {
    const fields = (ch.campos_entrada && ch.campos_entrada.length)
      ? ch.campos_entrada
      : [ch.variable].filter(Boolean);
    return `<div class="studio-queue-item">
      <span class="studio-plan-mark" style="background:var(--color-ink);color:#fff;">✓</span>
      <div style="min-width:0;">
        <div class="studio-plan-regla">${esc(ch.name)}${ch.bcbs239 ? ` <span class="studio-bcbs-inline">${esc(ch.bcbs239)}</span>` : ''}</div>
        <div style="font-size:15px;color:var(--color-body);margin-top:4px;">${esc(ch.desc || ch.condicion_error || '')}</div>
        <div class="studio-fields">${fields.length ? fields.map((f) => `<span class="studio-field-chip">${esc(f)}</span>`).join('') : ''}</div>
      </div>
      <div style="text-align:right;white-space:nowrap;">
        <div class="studio-plan-casos-num">${ch.casos ?? ch.n_casos ?? '—'}</div>
        <div class="studio-plan-casos-label">incidencias</div>
      </div>
    </div>`;
  }).join('');
}

/* ── data loaders ────────────────────────────────────────────────────────── */
async function loadChecks(projectId) {
  if (DEMO) {
    state.checks = DEMO_SEED.map((c) => ({ ...c }));
    return;
  }
  const q = projectId ? '?project_id=' + encodeURIComponent(projectId) : '';
  state.checks = await api('/dqc/checks' + q);
}

async function loadCurrentCases(checkId) {
  if (DEMO) return;
  try {
    const payload = await api('/dqc/checks/' + encodeURIComponent(checkId) + '/cases');
    state.currentCases = payload && payload.available ? payload : null;
  } catch { state.currentCases = null; }
}

async function saveFeedback(checkId, text) {
  if (DEMO) {
    state.checks = state.checks.map((c) => c.id === checkId ? { ...c, feedback: text } : c);
    render(); return;
  }
  await api('/dqc/checks/' + encodeURIComponent(checkId) + '/feedback', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ feedback: text }),
  });
  state.checks = state.checks.map((c) => c.id === checkId ? { ...c, feedback: text } : c);
}

async function generateExplanation(checkId) {
  if (DEMO) {
    const seed = DEMO_SEED.find((c) => c.id === checkId);
    if (seed) state.checks = state.checks.map((c) => c.id === checkId ? { ...c, explicacion: seed.explicacion } : c);
    render(); return;
  }
  const expl = await api('/dqc/checks/' + encodeURIComponent(checkId) + '/explain', { method: 'POST' });
  state.currentCases = { ...(state.currentCases || {}), explicacion: expl };
  render();
}

/* ── header ──────────────────────────────────────────────────────────────── */
function renderHeader() {
  const header = $('#studio-header');
  const bar = $('#studio-projectbar');
  if (state.screen === 'project') {
    bar.hidden = false;
    const c = counts();
    const project = projects.find((x) => x.id === currentProjectId);
    const files = (project && project.files) || [];
    bar.innerHTML = `
      <div class="studio-project-meta">
        <span class="studio-project-name">${esc(state.projectName)}</span>
        <span class="studio-project-table">${esc(state.projectTable)}</span>
      </div>
      <nav class="studio-nav">
        <button class="${state.projectTab === 'resumen' ? 'active' : ''}" data-tab="resumen">Resumen</button>
        <button class="${state.projectTab === 'generar' ? 'active' : ''}" data-tab="generar">Generar</button>
        <button class="${state.projectTab === 'revisar' ? 'active' : ''}" data-tab="revisar">Revisar<span class="nav-badge">${c.pending}</span></button>
      </nav>
      <div class="studio-files-wrap">
        <button class="studio-files-toggle" id="toggle-files" title="Archivos del proyecto" aria-expanded="${state.showFiles}">⧉</button>
        ${state.showFiles ? `<div class="studio-files-panel">
          <div class="studio-files-head">Archivos del proyecto <span>${files.length}</span></div>
          ${files.length ? files.map((f) => `
            <div class="studio-files-item">
              <span class="studio-files-icon">${fileIcon(f.type)}</span>
              <span class="studio-files-name">${esc(f.name)}</span>
              <span class="studio-files-meta">${fmtSize(f.size)}${f.addedAt ? ' · ' + esc(f.addedAt) : ''}</span>
            </div>`).join('') : '<div class="studio-files-empty">Sin archivos adjuntos.</div>'}
        </div>` : ''}
      </div>
      <button class="studio-exit" id="exit-project">Salir del proyecto</button>`;
    bar.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => { state.projectTab = b.dataset.tab; state.reviewIdx = 0; render(); }));
    $('#toggle-files').addEventListener('click', () => { state.showFiles = !state.showFiles; render(); });
    $('#exit-project').addEventListener('click', () => { state.screen = 'projects'; currentProjectId = null; state.checks = []; state.showFiles = false; render(); });
  } else {
    bar.hidden = true;
  }
  const banner = $('#studio-banner');
  banner.hidden = !state.banner;
}

/* ── screens ─────────────────────────────────────────────────────────────── */
function renderProjects() {
  const main = $('#studio-main');
  const c = counts();
  const rows = projects.map((p) => `
    <div class="studio-projects-row" data-open="${p.id}" role="button" tabindex="0">
      <div style="min-width:0;">
        <div class="studio-projects-name">${esc(p.name)}</div>
        <div class="studio-projects-table">${esc(p.table)}</div>
      </div>
      <div class="studio-projects-meta"><span>Diccionario: ${esc(p.dict)}</span><span>Fuentes: ${esc(p.sources)}</span><span class="studio-muted">Archivos: ${(p.files && p.files.length) || 0}</span></div>
      <div style="display:flex;align-items:center;gap:20px;">
        <div class="studio-projects-count">
          <div class="studio-projects-count-num">${p.id === currentProjectId ? c.total : '—'}</div>
          <div class="studio-projects-count-label">controles</div>
        </div>
        <span class="studio-projects-arrow">→</span>
      </div>
    </div>`).join('');
  main.className = 'studio-main wide';
  main.innerHTML = `
    <h1 class="studio-h1-lg">Proyectos</h1>
    <p class="studio-lede">Un proyecto reúne el diccionario de campos, las fuentes de entrada y los controles de calidad generados a partir de ellos.</p>
    <div class="studio-rule"></div>
    <div style="margin-top:32px;">${rows}</div>
    <button class="studio-btn" id="new-project" style="margin-top:40px;">Nuevo proyecto</button>`;
  main.querySelectorAll('[data-open]').forEach((r) => r.addEventListener('click', () => openProject(r.dataset.open)));
  $('#new-project').addEventListener('click', () => { state.screen = 'wizard'; state.wizardStep = 1; render(); });
}

function renderWizard() {
  const main = $('#studio-main');
  main.className = 'studio-main narrow';
  const step2Color = state.wizardStep === 2 ? 'var(--color-text)' : 'var(--color-muted)';
  const filesMarkup = state.draftFiles.length ? `
    <div class="studio-wizard-files">
      ${state.draftFiles.map((f, i) => `
        <div class="studio-wizard-file">
          <span class="studio-files-icon">${fileIcon(f.type)}</span>
          <span class="studio-wizard-file-name">${esc(f.name)}</span>
          <span class="studio-files-meta">${fmtSize(f.size)}</span>
          <button class="studio-files-remove" data-remove-file="${i}" aria-label="Quitar ${esc(f.name)}">×</button>
        </div>`).join('')}
    </div>` : '';
  const stepMarkup = state.wizardStep === 1 ? `
    <h1 class="studio-h1">Datos del proyecto</h1>
    <p class="studio-lede-sm">Solo dos campos son obligatorios. Los archivos del proyecto se adjuntan aquí, al crear el proyecto.</p>
    <label class="studio-field">
      <span class="studio-field-label">Nombre del proyecto</span>
      <input type="text" class="studio-input" id="wiz-name" value="${esc(state.draftName)}" placeholder="Ciclos de recuperación — cartera 2026">
    </label>
    <label class="studio-field">
      <span class="studio-field-label">Tabla objetivo</span>
      <input type="text" class="studio-input studio-input-mono" id="wiz-table" value="${esc(state.draftTable)}">
    </label>
    <div class="studio-field">
      <span class="studio-field-label">Archivos del proyecto <span class="studio-muted" style="font-weight:400;text-transform:none;">(diccionario, funcional, casos…)</span></span>
      <label class="studio-file">${state.draftFiles.length ? '✓ ' + state.draftFiles.length + ' archivo(s)' : 'Añadir archivos…'}<input type="file" id="wiz-files" multiple hidden></label>
      ${filesMarkup}
    </div>
    <button class="studio-btn" id="wiz-continue">Continuar</button>
    <div style="margin-top:24px;"><button class="studio-link" id="wiz-cancel">Cancelar</button></div>` : `
    <h1 class="studio-h1">Revisar y crear</h1>
    <p class="studio-lede-sm">Esto es todo lo que el asistente usará. Si algo no cuadra, vuelve atrás.</p>
    <dl class="studio-dl">
      <div class="studio-dl-row"><dt class="studio-dt">Nombre</dt><dd class="studio-dd">${esc(state.draftName)}</dd></div>
      <div class="studio-dl-row"><dt class="studio-dt">Tabla objetivo</dt><dd class="studio-dd studio-dd-mono">${esc(state.draftTable)}</dd></div>
      <div class="studio-dl-row"><dt class="studio-dt">Archivos adjuntos</dt><dd class="studio-dd" style="font-size:18px;">${state.draftFiles.length ? state.draftFiles.map((f) => esc(f.name)).join(' · ') : 'Ninguno'}</dd></div>
    </dl>
    <button class="studio-btn" id="wiz-create">Crear proyecto</button>
    <div style="margin-top:24px;"><button class="studio-link" id="wiz-back">Volver al paso 1</button></div>`;
  main.innerHTML = `
    <div class="studio-steps">
      <div class="studio-step ${state.wizardStep === 1 ? 'active' : 'inactive'}">
        <div class="studio-step-label">Paso 1 de 2</div>
        <div class="studio-step-title">Datos del proyecto</div>
        <div class="studio-step-rule"></div>
      </div>
      <div class="studio-step ${state.wizardStep === 2 ? 'active' : 'inactive'}">
        <div class="studio-step-label">Paso 2 de 2</div>
        <div class="studio-step-title" style="color:${step2Color};">Revisar y crear</div>
      </div>
    </div>
    ${stepMarkup}`;
  if (state.wizardStep === 1) {
    $('#wiz-name').addEventListener('input', (e) => { state.draftName = e.target.value; });
    $('#wiz-table').addEventListener('input', (e) => { state.draftTable = e.target.value; });
    $('#wiz-files').addEventListener('change', (e) => {
      const files = Array.from(e.target.files || []);
      const meta = files.map((f) => ({ name: f.name, size: f.size, type: f.type || '', addedAt: new Date().toISOString().slice(0, 10) }));
      state.draftFiles = state.draftFiles.concat(meta);
      render();
    });
    main.querySelectorAll('[data-remove-file]').forEach((b) => b.addEventListener('click', () => {
      state.draftFiles = state.draftFiles.filter((_, i) => String(i) !== b.dataset.removeFile);
      render();
    }));
    $('#wiz-continue').addEventListener('click', () => { state.wizardStep = 2; render(); });
    $('#wiz-cancel').addEventListener('click', () => { state.screen = 'projects'; render(); });
  } else {
    $('#wiz-create').addEventListener('click', createProject);
    $('#wiz-back').addEventListener('click', () => { state.wizardStep = 1; render(); });
  }
}

function createProject() {
  const files = state.draftFiles.map((f) => ({ ...f }));
  const p = {
    id: 'p' + Date.now(), name: state.draftName, table: state.draftTable,
    dict: files.find((f) => /\.xlsx$/i.test(f.name))?.name || '—',
    sources: files.map((f) => f.name).join(' · '), files,
  };
  projects.push(p); saveProjects(projects);
  state.draftFiles = []; state.wizardStep = 1;
  openProject(p.id);
}

function openProject(id) {
  const p = projects.find((x) => x.id === id);
  if (!p) return;
  currentProjectId = id;
  state.projectName = p.name; state.projectTable = p.table;
  state.screen = 'project'; state.projectTab = 'resumen'; state.reviewIdx = 0;
  if (!DEMO && state.apiAvailable) { loadChecks(id).finally(render); }
  else render();
}

function renderResumen() {
  const main = $('#studio-main');
  const c = counts();
  const reviewedTotal = c.validated + c.rejected;
  const guide = c.total === 0
    ? { title: 'Genera los primeros controles', body: 'Escribe las reglas en lenguaje natural. El asistente hace el resto y te deja el razonamiento a la vista.', cta: 'Ir a Generar', tab: 'generar' }
    : c.pending > 0
      ? { title: 'Revisa ' + c.pending + (c.pending > 1 ? ' controles pendientes' : ' control pendiente'), body: 'De cada uno verás cómo se decidió, su consulta y los casos que detecta. Validas o rechazas y pasa al siguiente.', cta: 'Ir a Revisar', tab: 'revisar' }
      : { title: 'Todo revisado', body: c.validated + (c.validated > 1 ? ' controles validados' : ' control validado') + ', listos para el cuadro de mando.', cta: 'Copiar consultas validadas', tab: 'revisar' };
  const validatedPct = c.total ? (c.validated / c.total) * 100 : 0;
  const rejectedPct = c.total ? (c.rejected / c.total) * 100 : 0;
  const rows = state.checks.map((ch) => {
    const st = DEMO ? DEMO_STATUS[ch.status] : statusStyle(ch.status);
    return `<div class="studio-table-row checks" data-open-check="${esc(ch.id)}">
      <div><span class="studio-tag" style="background:${st.bg};color:${st.fg};">${st.estado}</span></div>
      <div style="min-width:0;"><div style="font-size:18px;font-weight:600;">${esc(ch.name)}${ch.bcbs239 ? ` <span class="studio-bcbs-inline">${esc(ch.bcbs239)}</span>` : ''}</div><div style="font-size:15px;color:var(--color-body);margin-top:2px;">${esc(ch.desc || '')}</div></div>
      <div class="studio-var">${esc(ch.variable || '')}</div>
      <div class="studio-count-cell">${ch.casos ?? ch.n_casos ?? ''}</div>
    </div>`;
  }).join('');
  const central = buildCentral();
  const centralIntro = c.validated
    ? 'Todos los controles validados (' + c.validated + ') en una sola consulta: devuelve una fila por control con el recuento de incidencias que detecta sobre la tabla objetivo.'
    : 'Aquí aparecerá la consulta única con todos los controles validados y su recuento de incidencias. Valida al menos un control en «Revisar».';
  main.className = 'studio-main wide';
  main.innerHTML = `
    <div class="studio-summary-grid">
      <div style="min-width:0;">
        <div style="font-size:14px;text-transform:uppercase;letter-spacing:0.08em;color:var(--color-muted);">Controles en este proyecto</div>
        <div class="studio-count">${c.total}</div>
        <div style="font-size:20px;color:var(--color-body);margin-top:12px;">${c.total === 0 ? 'Todavía no hay controles en este proyecto.' : reviewedTotal + ' de ' + c.total + ' revisados'}</div>
        <div class="studio-statusbar"><div class="seg-validated" style="width:${validatedPct}%;"></div><div class="seg-rejected" style="width:${rejectedPct}%;"></div><div class="seg-pending"></div></div>
        <div class="studio-legend">
          <span class="studio-legend-item"><span class="studio-legend-swatch" style="background:var(--color-ink);"></span>Validados ${c.validated}</span>
          <span class="studio-legend-item"><span class="studio-legend-swatch" style="background:var(--color-red);"></span>Rechazados ${c.rejected}</span>
          <span class="studio-legend-item"><span class="studio-legend-swatch" style="background:var(--color-amber);"></span>Pendientes ${c.pending}</span>
        </div>
      </div>
      <aside class="studio-next">
        <div class="studio-next-kicker">Siguiente paso</div>
        <h2 class="studio-next-title">${esc(guide.title)}</h2>
        <p class="studio-next-body">${esc(guide.body)}</p>
        <button class="studio-next-btn" id="next-action">${esc(guide.cta)}</button>
      </aside>
    </div>
    <h2 class="studio-h2" style="margin-top:56px;">Todos los controles</h2>
    <p style="margin:8px 0 20px;font-size:17px;color:var(--color-body);">Toca cualquier fila para abrir ese control en la revisión.</p>
    <div class="studio-table-head checks"><div>Estado</div><div>Control</div><div>Campo</div><div>Casos detectados</div></div>
    ${rows || '<p style="padding:24px 0;color:var(--color-muted);">Sin controles en este proyecto todavía.</p>'}
    <section style="margin-top:56px;">
      <h2 class="studio-h2">Consulta centralizada</h2>
      <p style="margin:8px 0 20px;font-size:17px;color:var(--color-body);max-width:62ch;text-wrap:pretty;">${esc(centralIntro)}</p>
      ${c.validated ? `<div class="studio-queue" style="margin:24px 0 8px;">${centralQueueRows()}</div>` : ''}
      <pre class="studio-sql">${esc(central)}</pre>
      <button class="studio-btn" id="download-query" style="margin-top:24px;">${c.validated ? 'Descargar consulta centralizada (.sql)' : 'Descargar consulta centralizada (aún sin controles validados)'}</button>
    </section>`;
  $('#next-action').addEventListener('click', () => { state.projectTab = guide.tab; state.reviewIdx = 0; render(); });
  $('#download-query').addEventListener('click', () => {
    const blob = new Blob([buildCentral()], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = 'dqc_consulta_centralizada.sql'; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  main.querySelectorAll('[data-open-check]').forEach((r) => r.addEventListener('click', () => {
    const id = r.dataset.openCheck;
    const pos = pendingList().findIndex((p) => p.id === id);
    state.projectTab = 'revisar'; state.reviewIdx = pos >= 0 ? pos : 0; render();
  }));
}

/* ── Generar (1b): una regla por fila, reconocimiento en vivo ──────────── */
const DEMO_FIELDS = ['PD_ESTIMADA', 'EAD_TOTAL', 'COD_GESTOR', 'EST_CICLO', 'IMP_PENDIENTE', 'FEC_INI_CICLO', 'FEC_FIN_CICLO', 'LGD_ESTIMADA', 'ECL', 'STAGE_IFRS9', 'NUM_CICLO', 'FEC_ALTA'];

function queueRules() {
  return state.queue.map((q) => q.text).filter(Boolean);
}

function demoRecognize() {
  const rules = queueRules();
  const results = rules.map((rule) => {
    const found = DEMO_FIELDS.filter((f) => rule.toUpperCase().includes(f));
    return { rule, campos: found, n_campos: found.length, ambiguity: found.length === 0, motivo: '' };
  });
  applyRecognition(results);
}

async function refreshRecognition() {
  if (DEMO) { demoRecognize(); return; }
  const rules = queueRules();
  if (!rules.length || !state.dictionaryFile) return;
  const fd = form({ rules: JSON.stringify(rules), table_name: state.projectTable, sheet: '' });
  fd.append('dictionary', state.dictionaryFile);
  try {
    const res = await api('/dqc/recognize', { method: 'POST', body: fd });
    applyRecognition(res.results || []);
  } catch (e) { /* live recognition is best-effort */ }
}

let recogTimer = null;
function scheduleRecognition() {
  clearTimeout(recogTimer);
  recogTimer = setTimeout(refreshRecognition, 350);
}

function applyRecognition(results) {
  const byRule = {};
  results.forEach((r) => { byRule[r.rule] = r; });
  state.queue.forEach((q) => {
    const r = byRule[q.text];
    if (r) { q.campos = r.campos; q.ambiguity = r.ambiguity; q.motivo = r.motivo || ''; }
  });
  render();
}

function addQueueRule() {
  const text = (state.queueInput || '').trim();
  if (!text) return;
  state.queue.push({ text, campos: [], ambiguity: true, motivo: '' });
  state.queueInput = '';
  scheduleRecognition(); render();
}

function renderGenerar() {
  const main = $('#studio-main');
  main.className = 'studio-main wide';
  const planMarkup = state.plan.length ? `
    <section style="margin-top:48px;">
      <div style="display:flex;align-items:baseline;gap:16px;border-bottom:2px solid var(--color-ink);padding-bottom:12px;flex-wrap:wrap;">
        <h2 class="studio-h2">Plan del asistente</h2>
        <span style="font-size:16px;color:var(--color-body);">${esc(state.generating ? 'Trabajando — puedes seguir el razonamiento paso a paso' : (state.genDone ? 'Terminado' : ''))}</span>
      </div>
      ${state.plan.map((it) => `
        <article class="studio-plan-item">
          <div class="studio-plan-grid">
            <div class="studio-plan-mark" style="background:${it.markBg};color:${it.markFg};">${it.mark}</div>
            <div style="min-width:0;">
              <div class="studio-plan-regla">${esc(it.regla)}${it.bcbs239 ? ` <span class="studio-bcbs-inline">${esc(it.bcbs239)}</span>` : ''}</div>
              <div class="studio-plan-fase">${esc(it.fase)}</div>
              ${it.trace && it.trace.length ? `<ol class="studio-trace-ol">${normaliseTrace(it.trace).map((t) => `<li style="--t-rule:${t.rule};"><span class="t-mark" style="color:${t.rule};">${t.mark}</span><span style="min-width:0;"><span class="t-label">${esc(t.label)}</span>${t.detail ? `<span class="t-detail">${esc(t.detail)}</span>` : ''}</span></li>`).join('')}</ol>` : ''}
            </div>
            <div style="text-align:right;white-space:nowrap;">
              <div class="studio-plan-casos-label">Casos</div>
              <div class="studio-plan-casos-num">${it.casos}</div>
            </div>
          </div>
        </article>`).join('')}
      ${state.genDone ? `
        <div class="studio-done-box">
          <div style="min-width:0;flex:1;">
            <div class="studio-done-title">${state.plan.length} ${state.plan.length === 1 ? 'control listo' : 'controles listos'}</div>
            <div class="studio-done-sub">Cada uno trae su razonamiento, su consulta SQL y los casos que detecta.</div>
          </div>
          <button class="studio-btn studio-btn-md" id="review-now">Revisar ahora</button>
        </div>` : ''}
    </section>` : '';
  const ruleCount = queueRules().length;
  const countLabel = ruleCount ? ' (' + ruleCount + ' regla' + (ruleCount === 1 ? '' : 's') + ')' : '';
  main.innerHTML = `
    <h1 class="studio-h1">Generar controles</h1>
    <p class="studio-lede-sm">Añade una regla y la app te dirá al momento qué campos del diccionario ha reconocido. Una regla ambigua se ve antes de generar, no después.</p>
    <div class="studio-file-row">
      <label class="studio-file">${state.dictionaryFile ? '✓ ' + esc(state.dictionaryFile.name) : 'Subir diccionario Excel (.xlsx)'}<input type="file" accept=".xlsx,.xls" id="dict-file" hidden></label>
      <label class="studio-file">${state.casesFile ? '✓ ' + esc(state.casesFile.name) : 'Excel de datos — casos (opcional)'}<input type="file" accept=".xlsx,.xls" id="cases-file" hidden></label>
      ${DEMO ? '<button class="studio-link" id="load-demo">Cargar diccionario de demostración</button>' : ''}
    </div>
    <div class="studio-mode">
      <div class="studio-queue-add">
        <input type="text" class="studio-input studio-input-mono" id="queue-input" placeholder="Escribe una regla…" value="${esc(state.queueInput)}">
        <button class="studio-btn studio-btn-md" id="queue-add">Añadir regla</button>
      </div>
      <div class="studio-queue">
        ${state.queue.map((q, i) => `
          <div class="studio-queue-item">
            <span class="studio-plan-mark" style="background:${q.ambiguity ? 'var(--color-accent-600)' : 'var(--color-ink)'};color:#fff;">${q.ambiguity ? '!' : '✓'}</span>
            <div style="min-width:0;">
              <div class="studio-plan-regla">${esc(q.text)}</div>
              <div class="studio-fields">${q.campos && q.campos.length ? q.campos.map((c) => `<span class="studio-field-chip">${esc(c)}</span>`).join('') : `<span class="studio-muted">${esc(q.motivo || 'sin campos reconocidos')}</span>`}</div>
            </div>
            <button class="studio-files-remove" data-rm-queue="${i}" title="Quitar">×</button>
          </div>`).join('') || '<p class="studio-muted">Sin reglas todavía. Añade la primera.</p>'}
      </div>
    </div>
    <button class="studio-btn" id="start-gen" ${state.generating ? 'disabled' : ''} style="margin-top:28px;">${state.generating ? 'Generando…' : 'Generar controles' + countLabel}</button>
    <div class="studio-error" id="gen-error" ${state.error ? '' : 'hidden'}>${state.error ? esc(state.error) : ''}</div>
    ${planMarkup}`;
  $('#dict-file').addEventListener('change', (e) => { state.dictionaryFile = e.target.files[0] || null; scheduleRecognition(); render(); });
  $('#cases-file').addEventListener('change', (e) => { state.casesFile = e.target.files[0] || null; render(); });
  $('#start-gen').addEventListener('click', () => startGenerate());
  wireGenerarEvents(main);
  if (DEMO) $('#load-demo').addEventListener('click', () => {
    fetch('assets/demo/diccionario_demo.xlsx').then((r) => r.blob()).then((b) => { state.dictionaryFile = new File([b], 'diccionario_demo.xlsx'); scheduleRecognition(); render(); });
  });
  if (state.genDone) $('#review-now').addEventListener('click', () => { state.projectTab = 'revisar'; state.reviewIdx = 0; render(); });
  scheduleRecognition();
}

function wireGenerarEvents(main) {
  const input = $('#queue-input');
  if (input) {
    input.addEventListener('input', (e) => { state.queueInput = e.target.value; });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); addQueueRule(); } });
  }
  const add = $('#queue-add');
  if (add) add.addEventListener('click', addQueueRule);
  main.querySelectorAll('[data-rm-queue]').forEach((b) => b.addEventListener('click', (e) => {
    e.stopPropagation();
    state.queue = state.queue.filter((_, i) => String(i) !== b.dataset.rmQueue);
    scheduleRecognition(); render();
  }));
}


function renderRevisar() {
  const main = $('#studio-main');
  const c = counts();
  const cur = current();
  main.className = 'studio-main narrow';
  if (!cur) {
    const emptyTitle = c.total === 0 ? 'Nada que revisar todavía' : 'Todo revisado';
    const emptyBody = c.total === 0
      ? 'Genera controles y aparecerán aquí uno a uno, con su razonamiento y sus casos.'
      : c.validated + (c.validated === 1 ? ' control validado' : ' controles validados') + ' y ' + c.rejected + ' rechazados. Las consultas validadas ya se pueden llevar al cuadro de mando.';
    const emptyCta = c.total === 0 ? 'Ir a Generar' : (c.validated ? 'Descargar consulta centralizada (.sql)' : 'Volver al resumen');
    main.innerHTML = `
      <div class="studio-empty">
        <h1>${emptyTitle}</h1>
        <p>${emptyBody}</p>
        <button class="studio-btn" id="empty-action">${emptyCta}</button>
      </div>`;
    $('#empty-action').addEventListener('click', () => {
      if (c.total === 0) { state.projectTab = 'generar'; render(); }
      else if (c.validated) {
        const blob = new Blob([buildCentral()], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'dqc_consulta_centralizada.sql'; document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else { state.projectTab = 'resumen'; render(); }
    });
    return;
  }
  // fetch the detected-cases payload for the current check once (real mode),
  // so the review can show examples, the trace and the case explanation.
  if (!DEMO && state.currentCasesForId !== cur.id) {
    state.currentCasesForId = cur.id;
    state.currentCases = null;
    loadCurrentCases(cur.id).then(() => render());
  }
  const casesPayload = DEMO ? cur : (state.currentCases || {});
  const pend = pendingList();
  const reviewedTotal = c.validated + c.rejected;
  const sev = cur.sev ? DEMO_SEV[cur.sev] : { bg: '#f8f4f4', fg: '#444141' };
  const bcbs = cur.bcbs239 || '';
  const trace = casesPayload.trace || cur.trace || [];
  const traceMarkup = trace.length ? `
    <section class="studio-review-section">
      <h2 class="studio-section-head">Cómo se decidió
        <button class="studio-trace-toggle" id="toggle-trace" type="button"
                aria-expanded="${state.showTrace ? 'true' : 'false'}">${state.showTrace ? 'Ocultar' : 'Mostrar'}</button>
      </h2>
      ${state.showTrace ? renderTraceTree(trace) : ''}
    </section>` : '';
  const cols = casesPayload.columnas || cur.cols || cur.columnas || [];
  const rows = (casesPayload.ejemplos || cur.rows || cur.ejemplos || []).map((row) => {
    const cells = Array.isArray(row) ? row : cols.map((c) => row[c] ?? '');
    return `<tr>${cells.map((cell) => `<td>${esc(cell)}</td>`).join('')}</tr>`;
  }).join('');
  const cases = casesPayload.n_casos ?? cur.casos ?? cur.n_casos ?? 0;
  const expl = casesPayload.explicacion || cur.explicacion;
  const explHasContent = !!(expl && (expl.explicacion || expl.factor_comun || expl.posible_causa || expl.recomendacion));
  const explMarkup = explHasContent ? `
    <div class="studio-expl">
      ${expl.explicacion ? `<p class="studio-expl-body">${esc(expl.explicacion)}</p>` : ''}
      ${expl.factor_comun ? `<div class="studio-expl-row"><span class="studio-expl-k">Factor común</span><span class="studio-expl-v">${esc(expl.factor_comun)}</span></div>` : ''}
      ${expl.posible_causa ? `<div class="studio-expl-row"><span class="studio-expl-k">Causa probable</span><span class="studio-expl-v">${esc(expl.posible_causa)}</span></div>` : ''}
      ${expl.recomendacion ? `<div class="studio-expl-row"><span class="studio-expl-k">Recomendación</span><span class="studio-expl-v">${esc(expl.recomendacion)}</span></div>` : ''}
    </div>` : `
    <div class="studio-expl-empty">
      <p class="studio-muted">Explica qué tienen en común los casos detectados y su causa probable.</p>
      <button class="studio-btn-outline studio-btn-md" id="gen-expl">Generar análisis de los casos</button>
    </div>`;
  const feedback = cur.feedback || '';
  main.innerHTML = `
    <div style="display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;">
      <span style="font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:var(--color-muted);">Control ${reviewedTotal + 1} de ${c.total}</span>
      <span style="font-size:14px;color:var(--color-muted);">${pend.length > 1 ? 'Quedan ' + pend.length + ' por revisar' : 'Último pendiente'}</span>
    </div>
    <div class="studio-review-progress"><div class="fill" style="width:${c.total ? (reviewedTotal / c.total) * 100 : 0}%;"></div></div>
    <div class="studio-review-head">
      <span class="studio-sev" style="background:${sev.bg};color:${sev.fg};">${esc(cur.sev || '')}</span>
      <span class="studio-mono" style="font-size:16px;color:var(--color-accent);">${esc(cur.variable || '')}</span>
      ${bcbs ? `<span class="studio-bcbs" title="BCBS 239">${esc(bcbs)}</span>` : ''}
    </div>
    <h1 class="studio-review-title">${esc(cur.name)}</h1>
    <p class="studio-review-desc">${esc(cur.desc || '')}</p>
    ${traceMarkup}
    <section class="studio-review-section">
      <h2 class="studio-section-head">Consulta SQL</h2>
      <pre class="studio-sql">${esc(cur.sql || '')}</pre>
    </section>
    <section class="studio-review-section">
      <h2 class="studio-section-head">Casos detectados — ${cases === 0 ? 'ninguno' : cases + ' filas'}</h2>
      <p style="margin:20px 0 16px;font-size:17px;color:var(--color-body);text-wrap:pretty;">${esc(cur.hint || cur.condicion_error || '')}</p>
      ${cols.length ? `<div class="studio-cases-wrap"><table class="studio-cases"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="studio-muted">Sin casos en el Excel de pruebas.</p>'}
    </section>
    <section class="studio-review-section">
      <h2 class="studio-section-head">Análisis de los casos</h2>
      ${cases > 0 ? explMarkup : '<p class="studio-muted">Sin casos que analizar todavía.</p>'}
    </section>
    <section class="studio-review-section">
      <h2 class="studio-section-head">Feedback</h2>
      <textarea class="studio-textarea" id="feedback" rows="3" placeholder="Deja aquí tu valoración, observaciones o correcciones sobre este control.">${esc(feedback)}</textarea>
      <button class="studio-btn studio-btn-md" id="save-feedback" style="margin-top:12px;">Guardar feedback</button>
    </section>
    <div class="studio-review-actions">
      <button class="studio-btn-validate" id="validate">Validar este control</button>
      <button class="studio-btn-reject" id="reject">Rechazar</button>
    </div>`;
  const traceBtn = $('#toggle-trace');
  if (traceBtn) traceBtn.addEventListener('click', () => { state.showTrace = !state.showTrace; render(); });
  $('#validate').addEventListener('click', () => setStatus(cur.id, 'validated'));
  $('#reject').addEventListener('click', () => setStatus(cur.id, 'rejected'));
  const explBtn = $('#gen-expl');
  if (explBtn) explBtn.addEventListener('click', () => generateExplanation(cur.id));
  $('#save-feedback').addEventListener('click', async () => {
    const txt = $('#feedback').value || '';
    try { await saveFeedback(cur.id, txt); } catch (e) { state.error = e.message; render(); }
  });
}

/* ── status helpers for real mode ────────────────────────────────────────── */
function statusStyle(status) {
  return { pending: { estado: 'Pendiente', bg: '#d7d3d3', fg: '#201e1d' }, validated: { estado: 'Validado', bg: '#201e1d', fg: '#ffffff' }, rejected: { estado: 'Rechazado', bg: '#ec3013', fg: '#ffffff' } }[status] || { estado: status, bg: '#f8f4f4', fg: '#444141' };
}

async function setStatus(id, status) {
  if (DEMO) {
    state.checks = state.checks.map((c) => c.id === id ? { ...c, status } : c);
    state.reviewIdx = 0; render(); return;
  }
  try {
    await api('/dqc/checks/' + encodeURIComponent(id) + '/status', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) });
    await loadChecks(currentProjectId); state.reviewIdx = 0; render();
  } catch (e) { state.error = e.message; render(); }
}

/* ── generate ────────────────────────────────────────────────────────────── */
function planFromDemo(seedIdx) {
  const seed = DEMO_SEED[seedIdx % DEMO_SEED.length];
  return { mark: '✓', markBg: '#201e1d', markFg: '#ffffff', markTxt: '✓', regla: state.rules.split('\n')[seedIdx % state.rules.split('\n').length] || 'Regla', fase: 'Control listo para revisar', casos: String(seed.casos), trace: seed.trace.map((t) => ({ mark: DEMO_MARKS[t.k].mark, rule: DEMO_MARKS[t.k].rule, label: t.label, detail: t.detail })) };
}

async function startGenerate() {
  if (state.generating) return;
  const lines = queueRules();
  state.error = '';
  if (!lines.length) {
    state.error = 'Añade al menos una regla a la cola antes de generar.';
    render(); return;
  }
  // The backend declares `dictionary` as a required File; without it the
  // request 422s and the failure used to disappear.
  if (!DEMO && !state.dictionaryFile) {
    state.error = 'Adjunta el diccionario de campos (.xlsx) antes de generar.';
    render(); return;
  }
  // sync the free-text backing field so the plan / demo path always has the rules
  state.rules = lines.join('\n');
  state.generating = true; state.genDone = false; state.plan = lines.map((r) => ({ regla: r, fase: 'En espera', casos: '—', trace: [], mark: '', markBg: 'var(--color-bg)', markFg: 'var(--color-text)' }));
  render();
  if (DEMO) { await demoGenerate(lines); return; }
  try {
    const fd = form({ instructions: state.rules, table_name: state.projectTable, project_id: currentProjectId });
    fd.append('dictionary', state.dictionaryFile);
    if (state.casesFile) fd.append('data_file', state.casesFile);
    await consumeStream('/dqc/generate_stream', fd, onStreamEvent);
  } catch (e) {
    state.error = e.message; state.generating = false; render();
  }
}

async function demoGenerate(lines) {
  const marks = { ok: { mark: '✓', rule: '#201e1d' }, warn: { mark: '!', rule: '#dd2b0f' }, bad: { mark: '✗', rule: '#ec3013' } };
  for (let i = 0; i < lines.length; i++) {
    const seed = DEMO_SEED[i % DEMO_SEED.length];
    const phases = DEMO_PHASES.map((ph) => ({ ...ph }));
    state.plan[i] = { ...state.plan[i], mark: '›', markBg: '#dd2b0f', markFg: '#ffffff', fase: phases[0].fase };
    for (let p = 0; p < phases.length; p++) {
      state.plan[i].fase = phases[p].fase;
      state.plan[i].trace.push({ mark: marks[phases[p].k].mark, rule: marks[phases[p].k].rule, label: phases[p].label, detail: phases[p].detail });
      render(); await sleep(700);
    }
    state.plan[i] = { ...state.plan[i], mark: '✓', markBg: '#201e1d', markFg: '#ffffff', fase: 'Control listo para revisar', casos: String(seed.casos) };
    render(); await sleep(500);
    state.checks.push({ ...seed, id: 'DQC_N' + (state.checks.length + 1), status: 'pending' });
  }
  state.generating = false; state.genDone = true; state.reviewIdx = 0; render();
}

function onStreamEvent(ev) {
  if (ev.type === 'plan') {
    state.plan = (ev.data.items || []).map((p) => ({ regla: p.regla, fase: p.accion || 'En espera', casos: '—', trace: [], mark: '', markBg: 'var(--color-bg)', markFg: 'var(--color-text)' }));
  } else if (ev.type === 'item') {
    const d = ev.data;
    const it = state.plan.find((p) => p.regla === d.regla || (d.id && p._id === d.id));
    if (!it) return;
    if (d.estado === 'en_curso') {
      it.mark = '›'; it.markBg = '#dd2b0f'; it.markFg = '#ffffff'; it.fase = faseLabel(d.fase);
      if (d.trace) it.trace = d.trace;
    } else if (d.estado === 'completado') {
      it.mark = '✓'; it.markBg = '#201e1d'; it.markFg = '#ffffff'; it.fase = 'Control listo para revisar';
      it.casos = d.validacion?.n_casos != null ? String(d.validacion.n_casos) : String((d.dqcs || []).length);
      it.bcbs239 = d.dqcs && d.dqcs[0] ? (d.dqcs[0].bcbs239 || '') : '';
      if (d.trace) it.trace = d.trace;
    } else if (d.estado === 'ambigua') {
      it.mark = '!'; it.markBg = '#dd2b0f'; it.markFg = '#ffffff'; it.fase = 'Ambigua — ' + (d.falta || '');
    } else if (d.estado === 'error') {
      it.mark = '✗'; it.markBg = '#ec3013'; it.markFg = '#ffffff'; it.fase = d.error || 'Error';
    }
    render();
  } else if (ev.type === 'done') {
    state.generating = false; state.genDone = true; state.reviewIdx = 0;
    refreshFromBackend();
  }
}
function faseLabel(f) {
  return { suficiencia: '¿Hay información suficiente?', generacion: 'Construyendo la consulta…', validacion: 'Probándola contra los casos…', juicio: 'Revisión semántica…', grounding: 'Muestreando valores…' }[f] || f || '';
}

/* ── SSE stream consumption (generate_stream) ─────────────────────────────── */
async function consumeStream(path, fd, onEvent) {
  const res = await fetch(API + path, { method: 'POST', body: fd });
  if (!res.ok) {
    let detail = res.statusText; try { detail = (await res.json()).detail; } catch {}
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
      const evLine = chunk.split('\n').find((l) => l.startsWith('event: '));
      const dataLine = chunk.split('\n').find((l) => l.startsWith('data: '));
      if (!evLine || !dataLine) continue;
      const type = evLine.slice(7);
      let data; try { data = JSON.parse(dataLine.slice(6)); } catch { continue; }
      onEvent({ type, data });
    }
  }
}

/* ── real-mode refresh after generation ───────────────────────────────────── */
async function refreshFromBackend() {
  try { await loadChecks(currentProjectId); render(); } catch {}
}

/* ── main render ─────────────────────────────────────────────────────────── */
function render() {
  renderHeader();
  const main = $('#studio-main');
  if (state.screen === 'projects') renderProjects();
  else if (state.screen === 'wizard') renderWizard();
  else if (state.screen === 'project') {
    if (state.projectTab === 'resumen') renderResumen();
    else if (state.projectTab === 'generar') renderGenerar();
    else renderRevisar();
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ── boot ────────────────────────────────────────────────────────────────── */
async function boot() {
  if (DEMO) {
    state.banner = true;
    const p = projects.find((x) => x.id === 'p1') || projects[0];
    openProject(p.id);
    state.checks = DEMO_SEED.map((c) => ({ ...c }));
    render();
    return;
  }
  // detect backend availability; fall back to demo seed if the API is unreachable
  try {
    await api('/health');
    state.apiAvailable = true;
    await loadChecks(currentProjectId);
  } catch {
    state.banner = true;
    state.apiAvailable = false;
    if (projects.length) openProject(projects[0].id);
    state.checks = DEMO_SEED.map((c) => ({ ...c }));
  }
  render();
}

boot();
