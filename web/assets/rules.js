/* Step 3 — rules and report for one revision.

   Everything on this screen comes from the API: the rules are the stored
   controls of this revision, the cases are what their queries returned on
   the uploaded table, and the validation flow is the agent's own trace.
   Nothing here is illustrative. */

const revisionId = requireRevision();

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

let revision = null;
let rules = [];
let selectedId = null;
let preview = null;

const $ = (id) => document.getElementById(id);

// ── loading ──────────────────────────────────────────────────────────────────

async function loadRevision() {
  revision = await api('/dqc/revisions/' + encodeURIComponent(revisionId));
  $('revisionName').textContent = 'Revisión: ' + revision.name;
  $('revisionDescription').textContent = revision.description;
  renderChips();
}

function renderChips() {
  const estado = {
    pendiente: 'Pendiente de ejecución',
    en_ejecucion: 'En ejecución',
    completada: 'Reglas ejecutadas',
    error: 'Con errores',
  }[revision.status] || revision.status;
  $('revisionChips').innerHTML = [
    `<div class="chip chip-primary">Estado global: ${escapeHtml(estado)}</div>`,
    `<div class="chip">Tabla: ${escapeHtml(revision.data_filename || '–')}</div>`,
    `<div class="chip">Filas: ${revision.data_rows}</div>`,
    `<div class="chip">Columnas: ${revision.data_columns}</div>`,
    `<div class="chip">Campos del diccionario: ${revision.dictionary_fields}</div>`,
    `<div class="chip">Reglas definidas: ${rules.length}</div>`,
  ].join('');
}

async function loadRules(selectId) {
  const data = await api('/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules');
  rules = data.rules;
  renderRules();
  renderChips();
  const wanted = selectId || selectedId;
  select(rules.some((r) => r.check_id === wanted) ? wanted
        : (rules[0] ? rules[0].check_id : null));
}

function renderRules() {
  $('rulesList').innerHTML = rules.map((rule) => {
    const estado = ESTADO_CONTROL[rule.status] || ESTADO_CONTROL.pending;
    const casos = rule.n_casos === null || rule.n_casos === undefined
      ? '' : `<div class="small-text">${rule.n_casos} caso(s)</div>`;
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
  }).join('') || '<div class="small-text">Todavía no hay reglas. Añade la primera arriba.</div>';
}

// ── detail panel ─────────────────────────────────────────────────────────────

function current() {
  return rules.find((r) => r.check_id === selectedId) || null;
}

function select(checkId) {
  selectedId = checkId;
  renderRules();
  renderDetail();
}

function renderDetail() {
  const rule = current();
  const estado = rule ? (ESTADO_CONTROL[rule.status] || ESTADO_CONTROL.pending) : null;
  $('detailStatus').textContent = estado ? estado.label : '–';
  $('validateButton').disabled = !rule || rule.status === 'validated';
  $('rejectButton').disabled = !rule || rule.status === 'rejected';

  if (!rule) {
    $('detailRuleText').textContent = 'Selecciona una regla para ver su detalle.';
    ['detailInterpretation', 'detailCondition', 'casesBox', 'detailExplanation']
      .forEach((id) => { $(id).textContent = '–'; });
    ['summaryCases', 'summaryPercent', 'summarySeverity'].forEach((id) => {
      $(id).textContent = '–';
    });
    $('summaryMetrics').textContent = '';
    $('commentsList').textContent = '';
    $('commentText').value = '';
    return;
  }

  $('detailRuleText').textContent = rule.description || rule.name;

  const campos = (rule.campos_entrada || []).join(', ') || '–';
  const atribuidos = rule.atribucion && rule.atribucion.campos
    ? rule.atribucion.campos.join(', ') : null;
  const citas = rule.atribucion && rule.atribucion.citas && rule.atribucion.citas.length
    ? rule.atribucion.citas.join(', ') : null;
  $('detailInterpretation').innerHTML =
    `<strong>Campos declarados:</strong> ${escapeHtml(campos)}<br/>` +
    (atribuidos ? `<strong>Campos que la consulta lee:</strong> ${escapeHtml(atribuidos)}<br/>` : '') +
    (citas ? `<strong>Referencia:</strong> ${escapeHtml(citas)}<br/>` : '') +
    `<strong>Tipo de control:</strong> ${escapeHtml(rule.tipo || rule.category || '–')}`;

  $('detailCondition').innerHTML =
    escapeHtml(rule.condicion_error || '–') +
    `<div class="small-text" style="margin-top:6px;">
        <strong>Consulta ejecutada:</strong><br/>
        <code>${escapeHtml(rule.sql)}</code>
     </div>`;

  renderCases(rule);
  renderSummary(rule);
  $('commentText').value = '';
  $('commentsList').textContent = rule.feedback
    ? 'Último comentario: ' + rule.feedback : 'Sin comentarios.';
  $('rerunMessage').textContent = '';
}

function renderCases(rule) {
  const cols = rule.columnas || [];
  const rows = rule.ejemplos || [];
  if (!cols.length || !rows.length) {
    $('casesBox').textContent = rule.n_casos === 0
      ? 'La consulta se ejecutó y no encontró ningún caso que incumpla la regla.'
      : 'Sin casos registrados para esta regla.';
    return;
  }
  $('casesBox').innerHTML = `<table>
      <thead><tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((row) =>
        `<tr>${cols.map((c) => `<td>${escapeHtml(row[c])}</td>`).join('')}</tr>`).join('')}</tbody>
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
    (casos === null || casos === undefined || !revision.data_rows)
      ? '–' : ((casos / revision.data_rows) * 100).toFixed(2).replace('.', ',') + ' %';
  $('summarySeverity').textContent = rule.severity || '–';
  $('summaryMetrics').textContent = rule.bcbs239 ? 'BCBS 239: ' + rule.bcbs239 : '';
  $('detailExplanation').textContent = rule.explicacion || 'Sin explicación registrada.';
}

// ── validation flow (the agent's real trace) ─────────────────────────────────

function stepClass(step) {
  if (step.estado === 'error') return 'step-error';
  if (step.estado === 'ambigua') return 'step-warn';
  if (step.resultado === 'no') return 'step-warn';
  return 'step-ok';
}

function openFlujo() {
  const rule = current();
  const trace = (rule && rule.trace) || [];
  if (!trace.length) {
    $('flujoTimeline').innerHTML =
      '<div class="small-text">Esta regla no tiene traza registrada.</div>';
  } else {
    $('flujoTimeline').innerHTML = trace.map((step, i) => {
      const title = PASO_LABEL[step.paso] || step.paso;
      const desc = step.pregunta || step.accion ||
        (step.estado ? 'Estado: ' + step.estado : '');
      return `<div class="timeline-step" data-step="${i}">
            <div class="step-icon ${stepClass(step)}">${i + 1}</div>
            <div class="step-title">${escapeHtml(title)}${
              step.intento ? ' (intento ' + step.intento + ')' : ''}</div>
            <div class="step-desc">${escapeHtml(desc)}</div>
        </div>` + (i < trace.length - 1 ? '<div class="timeline-arrow">→</div>' : '');
    }).join('');
  }
  $('flujoDetailBox').textContent = 'Pulsa en uno de los pasos del flujo para ver su detalle.';
  $('flujoModal').style.display = 'flex';
}

$('flujoTimeline').addEventListener('click', (e) => {
  const node = e.target.closest('.timeline-step');
  if (!node) return;
  document.querySelectorAll('.timeline-step').forEach((s) => s.classList.remove('active'));
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

// ── adding rules ─────────────────────────────────────────────────────────────

function leftMessage(text, isError) {
  const el = $('leftMessage');
  el.textContent = text;
  el.className = 'left-message' + (isError ? ' error' : '');
}

function renderPreview(data) {
  preview = data;
  $('reviewRuleText').textContent = $('newRule').value.trim();
  const ok = data.estado === 'completado' && data.dqc;
  $('confirmReviewButton').disabled = !ok;

  if (!ok) {
    const motivo = data.estado === 'ambigua'
      ? ('El asistente no tiene información suficiente: ' + (data.falta || 'sin detalle'))
      : ('No se pudo derivar una consulta válida: ' + (data.error || 'sin detalle'));
    $('reviewInterpretation').textContent = motivo;
    $('reviewCode').textContent = '–';
    $('reviewCases').textContent =
      'Añade contexto en el comentario y reejecuta la interpretación.';
    return;
  }

  const dqc = data.dqc;
  $('reviewInterpretation').innerHTML =
    `<strong>Descripción:</strong> ${escapeHtml(dqc.descripcion)}<br/>` +
    `<strong>Campos implicados:</strong> ${escapeHtml((dqc.campos_entrada || []).join(', ') || '–')}<br/>` +
    `<strong>Tipo de control:</strong> ${escapeHtml(dqc.tipo || '–')} · ` +
    `<strong>Severidad:</strong> ${escapeHtml(dqc.severidad || '–')}`;
  $('reviewCode').innerHTML =
    `${escapeHtml(dqc.condicion_error || '')}<br/><code>${escapeHtml(dqc.regla_sql)}</code>`;

  const val = data.validacion || {};
  $('reviewCases').textContent = val.ejecutada
    ? `${val.n_casos} caso(s) de ${revision.data_rows} fila(s) incumplen la regla.`
    : 'La consulta pasó la validación estática pero no se ejecutó sobre los datos.';
}

async function requestPreview(comentario) {
  const regla = $('newRule').value.trim();
  if (!regla) {
    leftMessage('Escribe una regla antes de iniciar la revisión.', true);
    return null;
  }
  return apiJson('/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules/preview',
                 'POST', { regla, comentario: comentario || '' });
}

$('addRuleButton').addEventListener('click', async () => {
  leftMessage('Interpretando la regla…', false);
  $('addRuleButton').disabled = true;
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
    $('addRuleButton').disabled = false;
  }
});

$('reejecutarReviewButton').addEventListener('click', async () => {
  $('reejecutarReviewButton').disabled = true;
  $('reviewInterpretation').textContent = 'Reinterpretando con tu comentario…';
  try {
    const data = await requestPreview($('reviewComment').value.trim());
    if (data) renderPreview(data);
  } catch (err) {
    $('reviewInterpretation').textContent = err.message;
  } finally {
    $('reejecutarReviewButton').disabled = false;
  }
});

$('confirmReviewButton').addEventListener('click', async () => {
  if (!preview) return;
  $('confirmReviewButton').disabled = true;
  try {
    const saved = await apiJson(
      '/dqc/revisions/' + encodeURIComponent(revisionId) + '/rules', 'POST',
      { preview_id: preview.preview_id, comentario: $('reviewComment').value.trim() });
    $('ruleReviewModal').style.display = 'none';
    $('newRule').value = '';
    leftMessage('Regla añadida.', false);
    await loadRevision();
    await loadRules(saved.check_id);
  } catch (err) {
    leftMessage(err.message, true);
    $('ruleReviewModal').style.display = 'none';
  } finally {
    $('confirmReviewButton').disabled = false;
  }
});

const JOB_POLL_MS = 1500;

/** Follow a batch to the end by polling its rows.

    The batch used to arrive as a live event stream from inside the
    request. It is a job now: the server answers immediately with an id
    and the work happens elsewhere, one worker per rule. Polling is what
    survives that move — and what survives a reload. */
function jobSummary(job) {
  const partes = [`${job.saved} regla(s) añadidas`];
  if (job.failed) partes.push(`${job.failed} sin resultado`);
  return partes.join(', ') + '.';
}

async function followJob(jobId) {
  for (;;) {
    const job = await api('/dqc/revisions/' + encodeURIComponent(revisionId) +
                          '/jobs/' + encodeURIComponent(jobId));
    const running = job.items.filter((i) => i.status === 'en_curso');
    const fase = running.length && running[0].fase ? ` (${running[0].fase})` : '';
    if (job.status === 'completado' || job.status === 'error') {
      // the caller reloads the list before announcing the result, so the
      // message never arrives before the rules it is talking about
      return job;
    }
    leftMessage(`${job.done} de ${job.total} regla(s) procesadas${fase}…`, false);
    await new Promise((done) => setTimeout(done, JOB_POLL_MS));
  }
}

$('uploadRulesFileButton').addEventListener('click', async () => {
  const file = $('rulesFile').files[0];
  if (!file) return leftMessage('Selecciona un fichero de reglas.', true);

  const payload = new FormData();
  payload.append('rules_file', file);
  $('uploadRulesFileButton').disabled = true;
  leftMessage('Enviando reglas…', false);
  try {
    const queued = await api('/dqc/revisions/' + encodeURIComponent(revisionId) +
                             '/rules/batch', { method: 'POST', body: payload });
    const job = await followJob(queued.job_id);
    await loadRevision();
    await loadRules();
    leftMessage(jobSummary(job), job.status === 'error');
  } catch (err) {
    leftMessage(err.message, true);
  } finally {
    $('uploadRulesFileButton').disabled = false;
  }
});

// ── review actions ───────────────────────────────────────────────────────────

async function setStatus(status) {
  try {
    await apiJson('/dqc/checks/' + encodeURIComponent(selectedId) + '/status',
                  'POST', { status });
    await loadRules(selectedId);
  } catch (err) {
    leftMessage(err.message, true);
  }
}

$('validateButton').addEventListener('click', () => setStatus('validated'));
$('rejectButton').addEventListener('click', () => setStatus('rejected'));

$('addCommentButton').addEventListener('click', async () => {
  const feedback = $('commentText').value.trim();
  if (!feedback || !selectedId) return;
  await apiJson('/dqc/checks/' + encodeURIComponent(selectedId) + '/feedback',
                'POST', { feedback });
  await loadRules(selectedId);
});

$('reejecutarButton').addEventListener('click', async () => {
  const motivo = $('reejecutarReason').value.trim();
  if (!selectedId) return;
  if (!motivo) {
    $('rerunMessage').textContent = 'Explica por qué quieres reejecutar la regla.';
    return;
  }
  $('reejecutarButton').disabled = true;
  $('rerunMessage').textContent = 'Reejecutando el control…';
  try {
    await apiJson('/dqc/revisions/' + encodeURIComponent(revisionId) +
                  '/rules/' + encodeURIComponent(selectedId) + '/rerun',
                  'POST', { motivo });
    $('reejecutarReason').value = '';
    // the reload repaints the detail panel (clearing this box), so the
    // message goes up last
    await loadRules(selectedId);
    $('rerunMessage').textContent = 'Control reejecutado con tu corrección.';
  } catch (err) {
    $('rerunMessage').textContent = err.message;
  } finally {
    $('reejecutarButton').disabled = false;
  }
});

// ── report ───────────────────────────────────────────────────────────────────

$('generateReportButton').addEventListener('click', async () => {
  const body = $('reportBody');
  body.innerHTML = '<div class="detail-box-modal">Generando informe…</div>';
  $('reportModal').style.display = 'flex';
  try {
    const report = await api('/dqc/revisions/' + encodeURIComponent(revisionId) + '/report');
    const c = report.counts;
    const rows = report.checks.map((check) => `<tr>
        <td>${escapeHtml(check.description || check.name)}</td>
        <td>${escapeHtml(check.severity)}</td>
        <td>${check.n_casos === null || check.n_casos === undefined ? '–' : check.n_casos}</td>
      </tr>`).join('');
    body.innerHTML = `
      <div class="detail-box-modal">
        <div class="detail-label-modal">Estado de la revisión</div>
        <div class="report-grid">
          <div><strong>Validadas</strong><br/>${c.validated}</div>
          <div><strong>Pendientes</strong><br/>${c.pending_visible}</div>
          <div><strong>Rechazadas</strong><br/>${c.rejected}</div>
          <div><strong>Filas analizadas</strong><br/>${revision.data_rows}</div>
        </div>
        ${c.pending_visible ? '<div class="detail-metrics-modal">Hay reglas pendientes de revisar: el informe solo incluye las validadas.</div>' : ''}
      </div>
      <div class="detail-box-modal">
        <div class="detail-label-modal">Controles validados</div>
        ${rows ? `<table><thead><tr><th>Control</th><th>Severidad</th><th>Casos</th></tr></thead>
                  <tbody>${rows}</tbody></table>`
               : '<div class="detail-metrics-modal">Ninguna regla validada todavía. Valida al menos una para incluirla en el informe.</div>'}
      </div>
      ${report.sql ? `<div class="detail-box-modal">
        <div class="detail-label-modal">Consulta centralizada</div>
        <pre class="sql-box">${escapeHtml(report.sql)}</pre>
        <div class="modal-actions">
          <button id="downloadSqlButton">Descargar .sql</button>
        </div>
      </div>` : ''}`;

    if (report.sql) {
      $('downloadSqlButton').addEventListener('click', () => {
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

// ── list interactions, tabs, modals ──────────────────────────────────────────

$('rulesList').addEventListener('click', async (e) => {
  const item = e.target.closest('.rule-item');
  if (!item) return;
  if (e.target.matches('.rule-delete')) {
    const rule = rules.find((r) => r.check_id === item.dataset.id);
    if (!window.confirm(`Eliminar la regla "${rule.description || rule.name}"?`)) return;
    await api('/dqc/checks/' + encodeURIComponent(rule.check_id), { method: 'DELETE' });
    if (selectedId === rule.check_id) selectedId = null;
    await loadRevision();
    await loadRules();
    return;
  }
  select(item.dataset.id);
});

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    document.querySelectorAll('.tab-content-section')
      .forEach((s) => s.classList.remove('active'));
    tab.classList.add('active');
    $('tab-' + tab.dataset.tab).classList.add('active');
  });
});

document.querySelectorAll('input[name="entryMode"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    const manual = radio.value === 'manual';
    $('manualEntry').style.display = manual ? 'block' : 'none';
    $('fileEntry').style.display = manual ? 'none' : 'block';
    leftMessage('', false);
  });
});

$('openFlujoButton').addEventListener('click', openFlujo);
$('closeFlujoModal').addEventListener('click', () => { $('flujoModal').style.display = 'none'; });
$('closeReviewModal').addEventListener('click', () => { $('ruleReviewModal').style.display = 'none'; });
$('closeReportModal').addEventListener('click', () => { $('reportModal').style.display = 'none'; });

const headerMenuButton = $('headerMenuButton');
const headerMenu = $('headerMenu');
headerMenuButton.addEventListener('click', (e) => {
  e.stopPropagation();
  headerMenu.style.display = headerMenu.style.display === 'block' ? 'none' : 'block';
});
document.addEventListener('click', (e) => {
  if (!headerMenu.contains(e.target) && !headerMenuButton.contains(e.target)) {
    headerMenu.style.display = 'none';
  }
});
$('menuDictionary').addEventListener('click', (e) => {
  e.preventDefault();
  window.location.href = 'dictionary.html?rev=' + encodeURIComponent(revisionId);
});

(async function start() {
  try {
    await loadRevision();
    await loadRules();
    // a batch started before a reload is still running somewhere
    const last = await api('/dqc/revisions/' + encodeURIComponent(revisionId) + '/jobs');
    if (last && last.job_id && last.status !== 'completado' && last.status !== 'error') {
      const job = await followJob(last.job_id);
      await loadRevision();
      await loadRules();
      leftMessage(jobSummary(job), job.status === 'error');
    }
  } catch (err) {
    leftMessage(err.message, true);
  }
})();
