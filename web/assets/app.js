/* Wiring for the four mockups — without editing them.
 *
 * The pages in this folder are the designs as delivered, byte for byte,
 * plus one <script src> line. Everything that makes them work lives here:
 * the API calls, the real content that replaces the placeholder rows, the
 * few controls the designs did not include, and the extra CSS rules.
 *
 * Each page ships its own inline demo script, which runs before this file
 * and has already attached listeners that show "en la versión con
 * backend…". Those cannot be removed by name — nobody kept a reference to
 * them — so `fresh()` replaces the node with a clone of itself, which
 * carries the markup and none of the listeners. It is a blunt instrument,
 * used deliberately: the alternative is editing the designs.
 *
 * What is NOT touched, and stays as the mockup left it: every style rule
 * the designs define, their copy, their links, and the demo behaviour
 * that happens to be right already (the three-dot menu, the manual/file
 * radio toggle, the modal close buttons).
 */

const API = '';

// ── HTTP ─────────────────────────────────────────────────────────────────────

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch (_) {
    body = text;
  }
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

// ── small helpers ────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

function param(name) {
  return new URLSearchParams(window.location.search).get(name) || '';
}

/** Every step after the first is revision-scoped; without one there is
    nothing to show, so go back to the listing. */
function requireRevision() {
  const rev = param('rev');
  if (!rev) window.location.href = 'home.html';
  return rev;
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(iso) {
  if (!iso) return '–';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

/** Replace a node with a listener-free clone and return the new node.
    This is how the mockups' demo handlers are discarded without editing
    the HTML that registered them. */
function fresh(node) {
  if (!node) return null;
  const clone = node.cloneNode(true);
  node.replaceWith(clone);
  return clone;
}

function freshAll(selector) {
  return Array.from(document.querySelectorAll(selector)).map(fresh);
}

/** Style rules the wiring needs that the designs do not define. Injected
    rather than added to their <style> block, so the designs stay as they
    were delivered. */
function injectStyles(css) {
  const style = document.createElement('style');
  style.dataset.source = 'wiring';
  style.textContent = css;
  document.head.appendChild(style);
}

/** The designs reference pwc-logo.png, which this repo does not ship —
    drop your own into web/ and it appears. Until then, hide the broken
    image rather than showing a torn-page icon in the header. */
function hideMissingLogo() {
  document.querySelectorAll('.logo img').forEach((img) => {
    const hide = () => {
      img.style.visibility = 'hidden';
    };
    img.addEventListener('error', hide);
    if (img.complete && img.naturalWidth === 0) hide();
  });
}

// ── listing ──────────────────────────────────────────────────────────────────

const ESTADO_REVISION = {
  pendiente: { label: 'Pendiente', cls: 'status-pending' },
  en_ejecucion: { label: 'En ejecución', cls: 'status-pending' },
  completada: { label: 'Completada', cls: 'status-complete' },
  error: { label: 'Error ejecución', cls: 'status-error' },
};

function initHome() {
  injectStyles(`
    .chip-active { background: var(--primary); color: #ffffff; }
    .link-danger { color: var(--text-muted); margin-left: 10px; }
  `);

  const table = document.querySelector('table');
  const tbody = table.querySelector('tbody');
  const chips = document.querySelector('.chips');
  const search = document.querySelector('.search-box input');

  // the design shows the empty state as an HTML comment; make it real
  const empty = document.createElement('div');
  empty.className = 'empty-state';
  empty.textContent = 'Cargando revisiones…';
  table.after(empty);

  let revisions = [];
  let filter = '';

  function render() {
    const counts = {};
    revisions.forEach((r) => {
      counts[r.status] = (counts[r.status] || 0) + 1;
    });
    chips.innerHTML =
      `<span class="chip">Total: ${revisions.length}</span>` +
      Object.entries(ESTADO_REVISION)
        .map(
          ([key, meta]) =>
            `<span class="chip chip-clickable${filter === key ? ' chip-active' : ''}"
               data-status="${key}">${meta.label}: ${counts[key] || 0}</span>`,
        )
        .join('');

    const needle = search.value.trim().toLowerCase();
    const shown = revisions.filter((rev) => {
      if (filter && rev.status !== filter) return false;
      if (!needle) return true;
      return (rev.name + ' ' + (rev.data_filename || ''))
        .toLowerCase()
        .includes(needle);
    });

    tbody.innerHTML = shown
      .map((rev) => {
        const meta = ESTADO_REVISION[rev.status] || ESTADO_REVISION.pendiente;
        const next = rev.dictionary_filename
          ? `rules.html?rev=${encodeURIComponent(rev.revision_id)}`
          : `dictionary.html?rev=${encodeURIComponent(rev.revision_id)}`;
        const label = rev.dictionary_filename
          ? rev.rules_total
            ? 'Ver resultados'
            : 'Definir reglas'
          : 'Continuar (diccionario)';
        return `<tr>
          <td>${escapeHtml(rev.name)}</td>
          <td>${escapeHtml(rev.data_filename || '–')}</td>
          <td><span class="status-pill ${meta.cls}">${meta.label}</span></td>
          <td>${formatDate(rev.updated_at || rev.created_at)}</td>
          <td>
            <a href="${next}" class="link-secondary">${label}</a>
            <a href="#" class="link-secondary link-danger"
               data-delete="${escapeHtml(rev.revision_id)}">Eliminar</a>
          </td>
        </tr>`;
      })
      .join('');

    table.hidden = shown.length === 0;
    empty.hidden = shown.length > 0;
    empty.textContent = revisions.length
      ? 'Ninguna revisión coincide con el filtro.'
      : 'Aún no hay revisiones creadas. Haz clic en "Nueva revisión" para empezar.';
  }

  async function load() {
    try {
      revisions = await api('/dqc/revisions');
      render();
    } catch (err) {
      table.hidden = true;
      empty.hidden = false;
      empty.textContent = 'No se pudieron cargar las revisiones: ' + err.message;
    }
  }

  chips.addEventListener('click', (e) => {
    const chip = e.target.closest('[data-status]');
    if (!chip) return;
    filter = filter === chip.dataset.status ? '' : chip.dataset.status;
    render();
  });

  search.addEventListener('input', render);

  tbody.addEventListener('click', async (e) => {
    const link = e.target.closest('[data-delete]');
    if (!link) return;
    e.preventDefault();
    const rev = revisions.find((r) => r.revision_id === link.dataset.delete);
    if (!window.confirm(`Eliminar "${rev.name}" y sus ${rev.rules_total} regla(s)?`))
      return;
    await api('/dqc/revisions/' + encodeURIComponent(rev.revision_id), {
      method: 'DELETE',
    });
    load();
  });

  load();
}

// ── step 1: the table under review ───────────────────────────────────────────

function initNewRevision() {
  // the inline demo script owns this form's submit and the character
  // counter; the clone drops both so they can be done for real
  const form = fresh($('createRevisionForm'));
  const message = $('message');
  const submit = form.querySelector('button[type="submit"]');
  const nameEl = form.querySelector('#revisionName');
  const descriptionEl = form.querySelector('#description');
  const fileEl = form.querySelector('#csvFile');
  const helper = form.querySelector('#descriptionHelper');

  // the backend reads .xlsx as happily as .csv; without this the file
  // picker would hide half of what it accepts
  fileEl.accept = '.csv,.xlsx';

  function show(text, type) {
    message.textContent = text;
    message.className = 'message ' + (type || '');
    message.style.display = text ? 'block' : 'none';
  }

  descriptionEl.addEventListener('input', () => {
    helper.textContent =
      `Caracteres actuales: ${descriptionEl.value.length}. ` +
      'La descripción debe tener al menos 100 caracteres.';
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    show('', '');

    const name = nameEl.value.trim();
    const description = descriptionEl.value.trim();
    const file = fileEl.files[0];

    if (!name) return show('El nombre de la revisión es obligatorio.', 'error');
    if (description.length < 100) {
      return show(
        'La descripción de la tabla es obligatoria y debe tener al ' +
          'menos 100 caracteres.',
        'error',
      );
    }
    if (!file) return show('Debes subir el fichero de la BBDD.', 'error');
    if (!/\.(csv|xlsx)$/i.test(file.name)) {
      return show('El fichero debe ser .csv o .xlsx.', 'error');
    }

    const payload = new FormData();
    payload.append('name', name);
    payload.append('description', description);
    payload.append('data_file', file);

    submit.disabled = true;
    show('Leyendo la tabla…', '');
    try {
      const revision = await api('/dqc/revisions', { method: 'POST', body: payload });
      show(
        `Revisión creada: ${revision.data_rows} filas y ` +
          `${revision.data_columns} columnas. Pasando al diccionario…`,
        'success',
      );
      window.location.href =
        'dictionary.html?rev=' + encodeURIComponent(revision.revision_id);
    } catch (err) {
      show(err.message, 'error');
    } finally {
      submit.disabled = false;
    }
  });
}

// ── step 2: the dictionary ───────────────────────────────────────────────────

function initDictionary() {
  const revisionId = requireRevision();
  const form = fresh($('dictionaryForm'));
  const message = $('message');
  const submit = form.querySelector('button[type="submit"]');
  const fileEl = form.querySelector('#dictionaryFile');

  function show(text, type) {
    message.textContent = text;
    message.className = 'message ' + (type || '');
    message.style.display = text ? 'block' : 'none';
  }

  // which revision this dictionary belongs to, in the box the design
  // already reserves for messages
  api('/dqc/revisions/' + encodeURIComponent(revisionId))
    .then((rev) =>
      show(
        `Revisión "${rev.name}" · ${rev.data_filename} ` +
          `(${rev.data_rows} filas, ${rev.data_columns} columnas).`,
        '',
      ),
    )
    .catch((err) => show(err.message, 'error'));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = fileEl.files[0];
    if (!file) return show('Debes subir un fichero de diccionario.', 'error');

    const payload = new FormData();
    payload.append('dictionary', file);

    submit.disabled = true;
    show('Leyendo el diccionario…', '');
    try {
      const rev = await api(
        '/dqc/revisions/' + encodeURIComponent(revisionId) + '/dictionary',
        { method: 'POST', body: payload },
      );
      show(
        `Diccionario guardado: ${rev.dictionary_fields} campos reconocidos.`,
        'success',
      );
      window.location.href = 'rules.html?rev=' + encodeURIComponent(revisionId);
    } catch (err) {
      show(err.message, 'error');
    } finally {
      submit.disabled = false;
    }
  });
}

// ── step 3: rules and report ─────────────────────────────────────────────────

const ESTADO_CONTROL = {
  pending: { label: 'Pendiente', cls: 'status-pending' },
  validated: { label: 'Validada', cls: 'status-validated' },
  rejected: { label: 'Rechazada', cls: 'status-rejected' },
};

const PASO_LABEL = {
  suficiencia: 'Suficiencia',
  grounding: 'Valores reales',
  generacion: 'Generación de consulta',
  validacion: 'Validación',
  juicio: 'Juez semántico',
  atribucion: 'Atribución',
  explicacion: 'Explicación',
  resultado: 'Resultado',
};

const JOB_POLL_MS = 1500;

function initRules() {
  const revisionId = requireRevision();

  injectStyles(`
    .status-validated { background: #dcfce7; color: #166534; }
    .status-rejected  { background: #fee2e2; color: #991b1b; }
    .wiring-actions   { display: flex; gap: 8px; align-items: center; }
    .wiring-actions button {
      padding: 6px 10px; font-size: 11px; border: none;
      border-radius: 4px; cursor: pointer;
    }
    .wiring-validate { background: var(--primary); color: #ffffff; }
    .wiring-reject   { background: #f3f4f6; color: #374151; }
    .wiring-actions button:disabled { opacity: 0.5; cursor: default; }
    .wiring-grid {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 8px; margin-bottom: 10px;
    }
    pre.wiring-sql {
      margin: 0; padding: 8px; background: #f9fafb;
      border: 1px solid var(--border-gray); font-size: 11px;
      max-height: 220px; overflow: auto; white-space: pre-wrap;
    }
  `);

  // ── nodes whose demo listeners have to go
  const rulesList = fresh($('rulesList'));
  const addRuleButton = fresh($('addRuleButton'));
  const uploadRulesFileButton = fresh($('uploadRulesFileButton'));
  const addCommentButton = fresh($('addCommentButton'));
  const reejecutarButton = fresh($('reejecutarButton'));
  const generateReportButton = fresh($('generateReportButton'));
  const confirmReviewButton = fresh($('confirmReviewButton'));
  const reejecutarReviewButton = fresh($('reejecutarReviewButton'));
  const tabs = freshAll('.tab');
  const timeline = document.querySelector('.timeline'); // emptied below

  // ── controls the design does not have: the review decision
  const badge = document.querySelector('.detail-title-row .badge');
  const actions = document.createElement('div');
  actions.className = 'wiring-actions';
  badge.replaceWith(actions);
  actions.appendChild(badge);
  badge.textContent = '–';
  const validateButton = document.createElement('button');
  validateButton.className = 'wiring-validate';
  validateButton.textContent = 'Validar';
  validateButton.disabled = true;
  const rejectButton = document.createElement('button');
  rejectButton.className = 'wiring-reject';
  rejectButton.textContent = 'Rechazar';
  rejectButton.disabled = true;
  actions.append(validateButton, rejectButton);

  // ── and the report, which the design only had as an alert()
  document.body.insertAdjacentHTML(
    'beforeend',
    `
    <div id="wiringReportModal" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <div>
            <div class="modal-title">Informe de la revisión</div>
            <div class="modal-subtitle">
              Controles validados y consulta centralizada que los une en un
              único resultado.
            </div>
          </div>
          <button class="modal-close" id="wiringReportClose">&times;</button>
        </div>
        <div class="modal-body" id="wiringReportBody"></div>
      </div>
    </div>`,
  );

  const reportModal = $('wiringReportModal');
  $('wiringReportClose').addEventListener('click', () => {
    reportModal.style.display = 'none';
  });

  // ── state
  let revision = null;
  let rules = [];
  let selectedId = null;
  let preview = null;

  const current = () => rules.find((r) => r.check_id === selectedId) || null;

  function leftMessage(text, isError) {
    const el = $('leftMessage');
    el.textContent = text;
    el.className = 'left-message' + (isError ? ' error' : '');
  }

  // ── header
  async function loadRevision() {
    revision = await api('/dqc/revisions/' + encodeURIComponent(revisionId));
    document.querySelector('.review-info h1').textContent =
      'Revisión: ' + revision.name;
    document.querySelector('.review-info .subtitle').textContent = revision.description;
    renderChips();
    // keep the revision when navigating from the three-dot menu
    document.querySelectorAll('.header-menu a').forEach((link) => {
      const href = link.getAttribute('href') || '';
      if (href.startsWith('dictionary.html') || href.startsWith('rules.html')) {
        link.setAttribute(
          'href',
          href.split('?')[0] + '?rev=' + encodeURIComponent(revisionId),
        );
      }
    });
  }

  function renderChips() {
    const estado =
      {
        pendiente: 'Pendiente de ejecución',
        en_ejecucion: 'En ejecución',
        completada: 'Reglas ejecutadas',
        error: 'Con errores',
      }[revision.status] || revision.status;
    document.querySelector('.review-info .chips').innerHTML = [
      `<div class="chip chip-primary">Estado global: ${escapeHtml(estado)}</div>`,
      `<div class="chip">Tabla: ${escapeHtml(revision.data_filename || '–')}</div>`,
      `<div class="chip">Filas: ${revision.data_rows}</div>`,
      `<div class="chip">Columnas: ${revision.data_columns}</div>`,
      `<div class="chip">Campos del diccionario: ${revision.dictionary_fields}</div>`,
      `<div class="chip">Reglas definidas: ${rules.length}</div>`,
    ].join('');
  }

  // ── rules list
  async function loadRules(selectId) {
    const data = await api(
      '/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules',
    );
    rules = data.rules;
    renderRules();
    renderChips();
    const wanted = selectId || selectedId;
    select(
      rules.some((r) => r.check_id === wanted)
        ? wanted
        : rules[0]
          ? rules[0].check_id
          : null,
    );
  }

  function renderRules() {
    rulesList.innerHTML =
      rules
        .map((rule) => {
          const estado = ESTADO_CONTROL[rule.status] || ESTADO_CONTROL.pending;
          const casos =
            rule.n_casos === null || rule.n_casos === undefined
              ? ''
              : `<div class="small-text">${rule.n_casos} caso(s)</div>`;
          return `<div class="rule-item${rule.check_id === selectedId ? ' active' : ''}"
                   data-id="${escapeHtml(rule.check_id)}">
          <div class="rule-left">
              <div class="rule-text">${escapeHtml(rule.description || rule.name)}</div>
              ${casos}
          </div>
          <div class="rule-meta">
              <span class="rule-status ${estado.cls}">${estado.label}</span>
              <span class="rule-delete" data-action="delete">Eliminar</span>
          </div>
      </div>`;
        })
        .join('') ||
      '<div class="small-text">Todavía no hay reglas. Añade la primera arriba.</div>';
  }

  function select(checkId) {
    selectedId = checkId;
    renderRules();
    renderDetail();
  }

  // ── detail panel
  function renderDetail() {
    const rule = current();
    const estado = rule ? ESTADO_CONTROL[rule.status] || ESTADO_CONTROL.pending : null;
    badge.textContent = estado ? estado.label : '–';
    validateButton.disabled = !rule || rule.status === 'validated';
    rejectButton.disabled = !rule || rule.status === 'rejected';

    const casesBox = document.querySelector('#tab-tabla .detail-box');
    if (!rule) {
      $('detailRuleText').textContent = 'Selecciona una regla para ver su detalle.';
      $('detailInterpretation').textContent = '–';
      $('detailCondition').textContent = '–';
      casesBox.textContent = '–';
      $('detailExplanation').textContent = '–';
      ['summaryCases', 'summaryPercent', 'summarySeverity'].forEach((id) => {
        $(id).textContent = '–';
      });
      $('commentsList').textContent = '';
      $('commentText').value = '';
      return;
    }

    $('detailRuleText').textContent = rule.description || rule.name;

    const campos = (rule.campos_entrada || []).join(', ') || '–';
    const atribuidos =
      rule.atribucion && rule.atribucion.campos
        ? rule.atribucion.campos.join(', ')
        : null;
    const citas =
      rule.atribucion && rule.atribucion.citas && rule.atribucion.citas.length
        ? rule.atribucion.citas.join(', ')
        : null;
    $('detailInterpretation').innerHTML =
      `<strong>Campos declarados:</strong> ${escapeHtml(campos)}<br/>` +
      (atribuidos
        ? `<strong>Campos que la consulta lee:</strong> ${escapeHtml(atribuidos)}<br/>`
        : '') +
      (citas ? `<strong>Referencia:</strong> ${escapeHtml(citas)}<br/>` : '') +
      `<strong>Tipo de control:</strong> ${escapeHtml(rule.tipo || rule.category || '–')}`;

    $('detailCondition').innerHTML =
      escapeHtml(rule.condicion_error || '–') +
      `<div class="small-text" style="margin-top:6px;">
          <strong>Consulta ejecutada:</strong><br/>
          <code>${escapeHtml(rule.sql)}</code>
       </div>`;

    renderCases(rule, casesBox);
    renderSummary(rule);
    $('commentText').value = '';
    $('commentsList').textContent = rule.feedback
      ? 'Último comentario: ' + rule.feedback
      : 'Sin comentarios.';
  }

  function renderCases(rule, box) {
    const cols = rule.columnas || [];
    const rows = rule.ejemplos || [];
    if (!cols.length || !rows.length) {
      box.textContent =
        rule.n_casos === 0
          ? 'La consulta se ejecutó y no encontró ningún caso que incumpla la regla.'
          : 'Sin casos registrados para esta regla.';
      return;
    }
    box.innerHTML = `<table>
        <thead><tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
        <tbody>${rows
          .map(
            (row) =>
              `<tr>${cols.map((c) => `<td>${escapeHtml(row[c])}</td>`).join('')}</tr>`,
          )
          .join('')}</tbody>
      </table>
      <div class="detail-metrics" style="margin-top:6px;">
        Muestra de ${rows.length} de ${rule.n_casos} caso(s) detectado(s).
      </div>`;
  }

  function renderSummary(rule) {
    const casos = rule.n_casos;
    $('summaryCases').textContent =
      casos === null || casos === undefined ? '–' : `${casos} registro(s)`;
    $('summaryPercent').textContent =
      casos === null || casos === undefined || !revision.data_rows
        ? '–'
        : ((casos / revision.data_rows) * 100).toFixed(2).replace('.', ',') + ' %';
    $('summarySeverity').textContent = rule.severity || '–';
    $('detailExplanation').textContent =
      rule.explicacion || 'Sin explicación registrada.';
  }

  // ── validation flow: the agent's real trace, in the design's timeline
  function stepClass(step) {
    if (step.estado === 'error') return 'step-error';
    if (step.estado === 'ambigua' || step.resultado === 'no') return 'step-warn';
    return 'step-ok';
  }

  function renderFlow() {
    const rule = current();
    const trace = (rule && rule.trace) || [];
    if (!trace.length) {
      timeline.innerHTML =
        '<div class="small-text">Esta regla no tiene traza registrada.</div>';
    } else {
      timeline.innerHTML = trace
        .map((step, i) => {
          const title = PASO_LABEL[step.paso] || step.paso;
          const desc =
            step.pregunta ||
            step.accion ||
            (step.estado ? 'Estado: ' + step.estado : '');
          return (
            `<div class="timeline-step" data-step="${i}">
              <div class="step-icon ${stepClass(step)}">${i + 1}</div>
              <div class="step-title">${escapeHtml(title)}${
                step.intento ? ' (intento ' + step.intento + ')' : ''
              }</div>
              <div class="step-desc">${escapeHtml(desc)}</div>
          </div>` + (i < trace.length - 1 ? '<div class="timeline-arrow">→</div>' : '')
          );
        })
        .join('');
    }
    $('flujoDetailBox').textContent =
      'Pulsa en uno de los pasos del flujo para ver su detalle.';
    $('flujoModal').style.display = 'flex';
  }

  timeline.addEventListener('click', (e) => {
    const node = e.target.closest('.timeline-step');
    if (!node) return;
    timeline
      .querySelectorAll('.timeline-step')
      .forEach((s) => s.classList.remove('active'));
    node.classList.add('active');
    const step = (current().trace || [])[Number(node.dataset.step)];
    const parts = [];
    if (step.pregunta) parts.push(step.pregunta + ' → ' + (step.resultado || '–'));
    if (step.detalle) parts.push(step.detalle);
    if (step.n_casos !== undefined && step.n_casos !== null) {
      parts.push(step.n_casos + ' caso(s) detectado(s).');
    }
    $('flujoDetailBox').textContent = parts.join('\n') || 'Sin detalle para este paso.';
  });

  // ── tabs (the design opens the flow modal from its own tab)
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      if (target === 'flujo') return renderFlow();
      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      document
        .querySelectorAll('.tab-content-section')
        .forEach((s) => s.classList.remove('active'));
      $('tab-' + target).classList.add('active');
    });
  });

  // ── adding a rule
  function renderPreview(data) {
    preview = data;
    $('reviewRuleText').textContent = $('newRule').value.trim();
    const ok = data.estado === 'completado' && data.dqc;
    confirmReviewButton.disabled = !ok;

    if (!ok) {
      $('reviewInterpretation').textContent =
        data.estado === 'ambigua'
          ? 'El asistente no tiene información suficiente: ' +
            (data.falta || 'sin detalle')
          : 'No se pudo derivar una consulta válida: ' + (data.error || 'sin detalle');
      $('reviewCode').textContent =
        'Añade contexto en el comentario y reejecuta la interpretación.';
      return;
    }

    const dqc = data.dqc;
    const val = data.validacion || {};
    $('reviewInterpretation').innerHTML =
      `<strong>Descripción:</strong> ${escapeHtml(dqc.descripcion)}<br/>` +
      `<strong>Campos implicados:</strong> ${escapeHtml((dqc.campos_entrada || []).join(', ') || '–')}<br/>` +
      `<strong>Tipo de control:</strong> ${escapeHtml(dqc.tipo || '–')} · ` +
      `<strong>Severidad:</strong> ${escapeHtml(dqc.severidad || '–')}`;
    $('reviewCode').innerHTML =
      `${escapeHtml(dqc.condicion_error || '')}<br/><code>${escapeHtml(dqc.regla_sql)}</code>` +
      `<div class="detail-metrics-modal" style="margin-top:6px;">` +
      (val.ejecutada
        ? `${val.n_casos} caso(s) de ${revision.data_rows} fila(s) incumplen la regla.`
        : 'La consulta pasó la validación estática pero no se ejecutó sobre los datos.') +
      `</div>`;
  }

  async function requestPreview(comentario) {
    const regla = $('newRule').value.trim();
    if (!regla) {
      leftMessage('Escribe una regla antes de iniciar la revisión.', true);
      return null;
    }
    return apiJson(
      '/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules/preview',
      'POST',
      { regla, comentario: comentario || '' },
    );
  }

  addRuleButton.addEventListener('click', async () => {
    leftMessage('Interpretando la regla…', false);
    addRuleButton.disabled = true;
    try {
      const data = await requestPreview('');
      if (!data) return;
      renderPreview(data);
      $('reviewComment').value = '';
      $('ruleReviewModal').style.display = 'flex';
      leftMessage('', false);
    } catch (err) {
      leftMessage(err.message, true);
    } finally {
      addRuleButton.disabled = false;
    }
  });

  reejecutarReviewButton.addEventListener('click', async () => {
    reejecutarReviewButton.disabled = true;
    $('reviewInterpretation').textContent = 'Reinterpretando con tu comentario…';
    try {
      const data = await requestPreview($('reviewComment').value.trim());
      if (data) renderPreview(data);
    } catch (err) {
      $('reviewInterpretation').textContent = err.message;
    } finally {
      reejecutarReviewButton.disabled = false;
    }
  });

  confirmReviewButton.addEventListener('click', async () => {
    if (!preview) return;
    confirmReviewButton.disabled = true;
    try {
      const saved = await apiJson(
        '/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules',
        'POST',
        { preview_id: preview.preview_id, comentario: $('reviewComment').value.trim() },
      );
      $('ruleReviewModal').style.display = 'none';
      $('newRule').value = '';
      await loadRevision();
      await loadRules(saved.check_id);
      leftMessage('Regla añadida.', false);
    } catch (err) {
      $('ruleReviewModal').style.display = 'none';
      leftMessage(err.message, true);
    } finally {
      confirmReviewButton.disabled = false;
    }
  });

  // ── a rules file is a job: poll it instead of holding the request open
  function jobSummary(job) {
    const parts = [`${job.saved} regla(s) añadidas`];
    if (job.failed) parts.push(`${job.failed} sin resultado`);
    return parts.join(', ') + '.';
  }

  async function followJob(jobId) {
    for (;;) {
      const job = await api(
        '/dqc/revisions/' +
          encodeURIComponent(revisionId) +
          '/jobs/' +
          encodeURIComponent(jobId),
      );
      if (job.status === 'completado' || job.status === 'error') return job;
      const running = job.items.filter((i) => i.status === 'en_curso');
      const fase = running.length && running[0].fase ? ` (${running[0].fase})` : '';
      leftMessage(`${job.done} de ${job.total} regla(s) procesadas${fase}…`, false);
      await new Promise((done) => setTimeout(done, JOB_POLL_MS));
    }
  }

  uploadRulesFileButton.addEventListener('click', async () => {
    const file = $('rulesFile').files[0];
    if (!file) return leftMessage('Selecciona un fichero de reglas.', true);

    const payload = new FormData();
    payload.append('rules_file', file);
    uploadRulesFileButton.disabled = true;
    leftMessage('Enviando reglas…', false);
    try {
      const queued = await api(
        '/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules/batch',
        { method: 'POST', body: payload },
      );
      const job = await followJob(queued.job_id);
      await loadRevision();
      await loadRules();
      leftMessage(jobSummary(job), job.status === 'error');
    } catch (err) {
      leftMessage(err.message, true);
    } finally {
      uploadRulesFileButton.disabled = false;
    }
  });

  // ── review decisions
  async function setStatus(status) {
    try {
      await apiJson(
        '/dqc/checks/' + encodeURIComponent(selectedId) + '/status',
        'POST',
        { status },
      );
      await loadRules(selectedId);
    } catch (err) {
      leftMessage(err.message, true);
    }
  }

  validateButton.addEventListener('click', () => setStatus('validated'));
  rejectButton.addEventListener('click', () => setStatus('rejected'));

  addCommentButton.addEventListener('click', async () => {
    const feedback = $('commentText').value.trim();
    if (!feedback || !selectedId) return;
    await apiJson(
      '/dqc/checks/' + encodeURIComponent(selectedId) + '/feedback',
      'POST',
      { feedback },
    );
    await loadRules(selectedId);
  });

  reejecutarButton.addEventListener('click', async () => {
    const motivo = $('reejecutarReason').value.trim();
    if (!selectedId) return;
    if (!motivo)
      return leftMessage('Explica por qué quieres reejecutar la regla.', true);

    reejecutarButton.disabled = true;
    leftMessage('Reejecutando el control…', false);
    try {
      await apiJson(
        '/dqc/revisions/' +
          encodeURIComponent(revisionId) +
          '/rules/' +
          encodeURIComponent(selectedId) +
          '/rerun',
        'POST',
        { motivo },
      );
      $('reejecutarReason').value = '';
      await loadRules(selectedId);
      leftMessage('Control reejecutado con tu corrección.', false);
    } catch (err) {
      leftMessage(err.message, true);
    } finally {
      reejecutarButton.disabled = false;
    }
  });

  // ── the report
  generateReportButton.addEventListener('click', async () => {
    const body = $('wiringReportBody');
    body.innerHTML = '<div class="detail-box-modal">Generando informe…</div>';
    reportModal.style.display = 'flex';
    try {
      const report = await api(
        '/dqc/revisions/' + encodeURIComponent(revisionId) + '/report',
      );
      const c = report.counts;
      const rows = report.checks
        .map(
          (check) => `<tr>
          <td>${escapeHtml(check.description || check.name)}</td>
          <td>${escapeHtml(check.severity)}</td>
          <td>${check.n_casos === null || check.n_casos === undefined ? '–' : check.n_casos}</td>
        </tr>`,
        )
        .join('');
      body.innerHTML = `
        <div class="detail-box-modal">
          <div class="detail-label-modal">Estado de la revisión</div>
          <div class="wiring-grid">
            <div><strong>Validadas</strong><br/>${c.validated}</div>
            <div><strong>Pendientes</strong><br/>${c.pending_visible}</div>
            <div><strong>Rechazadas</strong><br/>${c.rejected}</div>
            <div><strong>Filas analizadas</strong><br/>${revision.data_rows}</div>
          </div>
          ${c.pending_visible ? '<div class="detail-metrics-modal">Hay reglas pendientes de revisar: el informe solo incluye las validadas.</div>' : ''}
        </div>
        <div class="detail-box-modal">
          <div class="detail-label-modal">Controles validados</div>
          ${
            rows
              ? `<table><thead><tr><th>Control</th><th>Severidad</th><th>Casos</th></tr></thead>
                    <tbody>${rows}</tbody></table>`
              : '<div class="detail-metrics-modal">Ninguna regla validada todavía. Valida al menos una para incluirla en el informe.</div>'
          }
        </div>
        ${
          report.sql
            ? `<div class="detail-box-modal">
          <div class="detail-label-modal">Consulta centralizada</div>
          <pre class="wiring-sql">${escapeHtml(report.sql)}</pre>
          <div class="modal-actions">
            <button id="wiringDownloadSql">Descargar .sql</button>
          </div>
        </div>`
            : ''
        }`;

      if (report.sql) {
        $('wiringDownloadSql').addEventListener('click', () => {
          const blob = new Blob([report.sql], { type: 'application/sql' });
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = `informe_${revision.name.replace(/\W+/g, '_').toLowerCase()}.sql`;
          link.click();
          URL.revokeObjectURL(link.href);
        });
      }
    } catch (err) {
      body.innerHTML = `<div class="detail-box-modal">${escapeHtml(err.message)}</div>`;
    }
  });

  // ── list interactions
  rulesList.addEventListener('click', async (e) => {
    const item = e.target.closest('.rule-item');
    if (!item) return;
    if (e.target.matches('.rule-delete')) {
      const rule = rules.find((r) => r.check_id === item.dataset.id);
      if (!window.confirm(`Eliminar la regla "${rule.description || rule.name}"?`))
        return;
      await api('/dqc/checks/' + encodeURIComponent(rule.check_id), {
        method: 'DELETE',
      });
      if (selectedId === rule.check_id) selectedId = null;
      await loadRevision();
      await loadRules();
      return;
    }
    select(item.dataset.id);
  });

  (async function start() {
    try {
      await loadRevision();
      await loadRules();
      // a batch started before a reload is still running somewhere
      const last = await api(
        '/dqc/revisions/' + encodeURIComponent(revisionId) + '/jobs',
      );
      if (
        last &&
        last.job_id &&
        last.status !== 'completado' &&
        last.status !== 'error'
      ) {
        const job = await followJob(last.job_id);
        await loadRevision();
        await loadRules();
        leftMessage(jobSummary(job), job.status === 'error');
      }
    } catch (err) {
      leftMessage(err.message, true);
    }
  })();
}

// ── which page is this? ──────────────────────────────────────────────────────

hideMissingLogo();

if ($('rulesList')) initRules();
else if ($('createRevisionForm')) initNewRevision();
else if ($('dictionaryForm')) initDictionary();
else if (document.querySelector('.search-box input')) initHome();
