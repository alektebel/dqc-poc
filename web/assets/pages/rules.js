/* Step 3 — rules, results and report, with no backend of our own.
 *
 * Where each piece comes from now:
 *   - the rule → query step: your API (docs/API_CONTRACT.md), which is
 *     the only thing that reaches Bedrock;
 *   - running the query: SQLite compiled to WebAssembly, over the CSV that
 *     never left this machine;
 *   - revisions and controls: your API when configured, localStorage when
 *     not.
 *
 * The page is the mockup, untouched. Everything here reaches into it by
 * the ids and classes the design already had.
 */

import { hasApi } from '../config.js';
import * as api from '../lib/api.js';
import * as store from '../lib/store.js';
import * as files from '../lib/files.js';
import { parseCsv, parseDictionary, readFileText } from '../lib/csv.js';
import { Dataset } from '../lib/sqlite.js';
import { $, escapeHtml, fresh, freshAll, injectStyles, param } from '../lib/dom.js';

const ESTADO_CONTROL = {
  pending: { label: 'Pendiente', cls: 'status-pending' },
  validated: { label: 'Validada', cls: 'status-validated' },
  rejected: { label: 'Rechazada', cls: 'status-rejected' },
};

const PASO_LABEL = {
  suficiencia: 'Suficiencia',
  generacion: 'Generación de consulta',
  validacion: 'Validación',
  ejecucion: 'Ejecución',
  explicacion: 'Explicación',
  resultado: 'Resultado',
};

export async function initRules() {
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
    .wiring-banner {
      padding: 8px 10px; margin-bottom: 10px; font-size: 12px;
      background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412;
    }
    .wiring-load { margin-bottom: 12px; font-size: 12px; }
    .wiring-load label { display: block; margin: 6px 0 2px; font-weight: 600; }
    pre.wiring-sql {
      margin: 0; padding: 8px; background: #f9fafb;
      border: 1px solid var(--border-gray); font-size: 11px;
      max-height: 220px; overflow: auto; white-space: pre-wrap;
    }
    textarea.wiring-sql-input {
      width: 100%; min-height: 90px; font-family: monospace; font-size: 12px;
      padding: 6px; border: 1px solid var(--border-gray);
    }
  `);

  // ── drop the mockup's demo listeners
  const rulesList = fresh($('rulesList'));
  const addRuleButton = fresh($('addRuleButton'));
  const uploadRulesFileButton = fresh($('uploadRulesFileButton'));
  const addCommentButton = fresh($('addCommentButton'));
  const reejecutarButton = fresh($('reejecutarButton'));
  const generateReportButton = fresh($('generateReportButton'));
  const confirmReviewButton = fresh($('confirmReviewButton'));
  const reejecutarReviewButton = fresh($('reejecutarReviewButton'));
  const tabs = freshAll('.tab');
  const timeline = document.querySelector('.timeline');

  // ── the review decision, which the design does not include
  const badge = document.querySelector('.detail-title-row .badge');
  const actions = document.createElement('div');
  actions.className = 'wiring-actions';
  badge.replaceWith(actions);
  actions.appendChild(badge);
  badge.textContent = '–';
  const validateButton = Object.assign(document.createElement('button'), {
    className: 'wiring-validate',
    textContent: 'Validar',
    disabled: true,
  });
  const rejectButton = Object.assign(document.createElement('button'), {
    className: 'wiring-reject',
    textContent: 'Rechazar',
    disabled: true,
  });
  actions.append(validateButton, rejectButton);

  // ── the report modal, which the design only had as an alert()
  document.body.insertAdjacentHTML(
    'beforeend',
    `<div id="wiringReportModal" class="modal-overlay">
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
  let fields = [];
  let dataset = null;
  let rules = [];
  let selectedId = null;
  let preview = null;

  const current = () => rules.find((r) => r.check_id === selectedId) || null;

  function leftMessage(text, isError) {
    const el = $('leftMessage');
    el.textContent = text;
    el.className = 'left-message' + (isError ? ' error' : '');
  }

  function banner(text) {
    let el = document.querySelector('.wiring-banner');
    if (!el) {
      el = document.createElement('div');
      el.className = 'wiring-banner';
      document.querySelector('.entry-area').prepend(el);
    }
    el.innerHTML = text;
  }

  // ── loading the revision, its dictionary and its data
  async function loadContext() {
    const revisionId = param('rev');
    if (revisionId) {
      revision = await store.getRevision(revisionId);
    } else {
      revision = null;
    }

    const dataFile = revision
      ? await files.getFile(revision.revision_id, 'data')
      : null;
    const dictFile = revision
      ? await files.getFile(revision.revision_id, 'dictionary')
      : null;

    if (!revision || !dataFile || !dictFile) {
      await askForFiles(Boolean(revision), dataFile, dictFile);
      return false;
    }
    await useFiles(dataFile, dictFile);
    return true;
  }

  /** The files live in this browser only. Opened elsewhere — or with no
      revision at all — the page asks for them instead of failing. */
  function askForFiles(haveRevision, dataFile, dictFile) {
    return new Promise((resolve) => {
      const box = document.createElement('div');
      box.className = 'wiring-load';
      box.innerHTML = `
        <div class="wiring-banner">
          ${
            haveRevision
              ? 'Esta revisión existe, pero sus ficheros no están en este navegador: los datos nunca se suben a ningún sitio.'
              : 'No hay ninguna revisión abierta. Selecciona los ficheros para empezar una aquí mismo.'
          }
        </div>
        ${dataFile ? '' : '<label>Tabla de datos (.csv)</label><input type="file" accept=".csv" id="wiringData" />'}
        ${dictFile ? '' : '<label>Diccionario de campos (.csv)</label><input type="file" accept=".csv" id="wiringDict" />'}
        <button id="wiringLoad" style="margin-top:8px;">Cargar</button>
      `;
      document.querySelector('.entry-area').prepend(box);

      $('wiringLoad').addEventListener('click', async () => {
        try {
          const dataInput = $('wiringData');
          const dictInput = $('wiringDict');
          const nextData = dataInput
            ? { filename: dataInput.files[0]?.name, file: dataInput.files[0] }
            : null;
          const nextDict = dictInput
            ? { filename: dictInput.files[0]?.name, file: dictInput.files[0] }
            : null;
          if ((dataInput && !nextData.file) || (dictInput && !nextDict.file)) {
            return leftMessage('Selecciona los dos ficheros.', true);
          }

          const dataRecord = nextData
            ? { filename: nextData.filename, text: await readFileText(nextData.file) }
            : dataFile;
          const dictRecord = nextDict
            ? { filename: nextDict.filename, text: await readFileText(nextDict.file) }
            : dictFile;

          // parse before storing anything, so a bad file changes nothing
          const table = parseCsv(dataRecord.text);
          const parsedFields = parseDictionary(dictRecord.text);

          if (!revision) {
            revision = await store.createRevision({
              name: dataRecord.filename.replace(/\.csv$/i, ''),
              description: 'Revisión creada desde la pantalla de reglas.',
              table_name: dataRecord.filename
                .replace(/\.csv$/i, '')
                .replace(/\W+/g, '_'),
              data_filename: dataRecord.filename,
              data_rows: table.rows.length,
              data_columns: table.headers.length,
              dictionary_filename: dictRecord.filename,
              dictionary_fields: parsedFields.length,
            });
            const url = new URL(window.location.href);
            url.searchParams.set('rev', revision.revision_id);
            window.history.replaceState({}, '', url);
          } else {
            revision = await store.updateRevision(revision.revision_id, {
              data_filename: dataRecord.filename,
              data_rows: table.rows.length,
              data_columns: table.headers.length,
              dictionary_filename: dictRecord.filename,
              dictionary_fields: parsedFields.length,
            });
          }

          await files.putFile(revision.revision_id, 'data', dataRecord);
          await files.putFile(revision.revision_id, 'dictionary', dictRecord);
          box.remove();
          await useFiles(dataRecord, dictRecord);
          await start();
          resolve(true);
        } catch (err) {
          leftMessage(err.message, true);
        }
      });
    });
  }

  async function useFiles(dataRecord, dictRecord) {
    const table = parseCsv(dataRecord.text);
    fields = parseDictionary(dictRecord.text);
    if (dataset) dataset.close();
    dataset = await Dataset.fromCsv(table, revision.table_name || 'tabla');
  }

  // ── header
  function renderHeader() {
    document.querySelector('.review-info h1').textContent =
      'Revisión: ' + revision.name;
    document.querySelector('.review-info .subtitle').textContent = revision.description;
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
      `<div class="chip">Campos del diccionario: ${fields.length}</div>`,
      `<div class="chip">Reglas definidas: ${rules.length}</div>`,
    ].join('');

    document.querySelectorAll('.header-menu a').forEach((link) => {
      const href = link.getAttribute('href') || '';
      if (href.startsWith('dictionary.html') || href.startsWith('rules.html')) {
        link.setAttribute(
          'href',
          href.split('?')[0] + '?rev=' + encodeURIComponent(revision.revision_id),
        );
      }
    });

    const where = store.usingApi()
      ? 'Guardando en tu API.'
      : '<strong>Modo local</strong>: sin API configurada, las reglas se guardan solo en este navegador ' +
        'y la consulta la escribes tú. Rellena <code>web/assets/config.js</code> para conectar el modelo.';
    banner(`${where} Los ficheros nunca salen de esta máquina.`);
  }

  // ── rules list
  async function loadRules(selectId) {
    rules = await store.listChecks(revision.revision_id);
    renderRules();
    renderHeader();
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
                  <div class="rule-text">${escapeHtml(rule.descripcion || rule.regla)}</div>
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

  // ── detail
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

    $('detailRuleText').textContent = rule.regla || rule.descripcion;
    $('detailInterpretation').innerHTML =
      `<strong>Descripción:</strong> ${escapeHtml(rule.descripcion || '–')}<br/>` +
      `<strong>Campos implicados:</strong> ${escapeHtml((rule.campos_entrada || []).join(', ') || '–')}<br/>` +
      `<strong>Tipo de control:</strong> ${escapeHtml(rule.tipo || '–')}`;
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
    $('summarySeverity').textContent = rule.severidad || '–';
    $('detailExplanation').textContent =
      rule.explicacion || 'Sin explicación registrada.';
  }

  // ── validation flow
  function stepClass(step) {
    if (step.estado === 'error') return 'step-error';
    if (step.estado === 'ambigua' || step.resultado === 'no') return 'step-warn';
    return 'step-ok';
  }

  function renderFlow() {
    const rule = current();
    const trace = (rule && rule.trace) || [];
    timeline.innerHTML = trace.length
      ? trace
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
              </div>` +
              (i < trace.length - 1 ? '<div class="timeline-arrow">→</div>' : '')
            );
          })
          .join('')
      : '<div class="small-text">Esta regla no tiene traza registrada.</div>';
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

  // ── adding a rule: interpret (API) or ask for the query (local)
  function executeOnData(sql, trace) {
    const result = dataset.run(sql, revision.table_name);
    trace.push({
      paso: 'ejecucion',
      pregunta: '¿La consulta se ejecuta sobre los datos?',
      resultado: result.ok ? 'si' : 'no',
      detalle: result.ok
        ? `${result.n_casos} caso(s) de ${dataset.nRows} fila(s)`
        : result.error,
    });
    return result;
  }

  function showPreview(data) {
    preview = data;
    $('reviewRuleText').textContent = data.regla;
    const ok = data.estado === 'completado';
    confirmReviewButton.disabled = !ok;

    if (!ok) {
      $('reviewInterpretation').textContent =
        data.estado === 'ambigua'
          ? 'El asistente no tiene información suficiente: ' +
            (data.falta || 'sin detalle')
          : 'No se pudo derivar una consulta válida: ' + (data.error || 'sin detalle');
      $('reviewCode').textContent =
        'Corrige el comentario y reejecuta la interpretación.';
      return;
    }

    $('reviewInterpretation').innerHTML =
      `<strong>Descripción:</strong> ${escapeHtml(data.descripcion || '–')}<br/>` +
      `<strong>Campos implicados:</strong> ${escapeHtml((data.campos_entrada || []).join(', ') || '–')}<br/>` +
      `<strong>Tipo de control:</strong> ${escapeHtml(data.tipo || '–')} · ` +
      `<strong>Severidad:</strong> ${escapeHtml(data.severidad || '–')}`;
    $('reviewCode').innerHTML =
      `${escapeHtml(data.condicion_error || '')}<br/><code>${escapeHtml(data.sql)}</code>` +
      `<div class="detail-metrics-modal" style="margin-top:6px;">` +
      `${data.n_casos} caso(s) de ${dataset.nRows} fila(s) incumplen la regla.</div>`;
  }

  /** Without an API nobody can derive the query, so the reviewer writes
      it. The rest of the flow — execution, cases, report — is identical. */
  function askForQuery(regla) {
    $('reviewRuleText').textContent = regla;
    $('reviewInterpretation').innerHTML =
      'No hay modelo configurado, así que la consulta la escribes tú. ' +
      'Se ejecutará sobre tu fichero igual que si la hubiera derivado el asistente.' +
      `<div class="small-text" style="margin-top:6px;">Tabla: <code>${escapeHtml(
        revision.table_name,
      )}</code> · Campos: ${escapeHtml(fields.map((f) => f.nombre).join(', '))}</div>`;
    $('reviewCode').innerHTML = `<textarea class="wiring-sql-input" id="wiringSqlInput"
         placeholder="SELECT ${escapeHtml(fields[0]?.nombre || 'ID')} FROM ${escapeHtml(
           revision.table_name,
         )} WHERE …"></textarea>
       <button id="wiringRunSql" style="margin-top:6px;">Ejecutar sobre mis datos</button>
       <div id="wiringSqlResult" class="detail-metrics-modal" style="margin-top:6px;"></div>`;
    confirmReviewButton.disabled = true;
    preview = null;

    $('wiringRunSql').addEventListener('click', () => {
      const sql = $('wiringSqlInput').value.trim();
      if (!sql) return;
      const trace = [];
      const result = executeOnData(sql, trace);
      if (!result.ok) {
        $('wiringSqlResult').textContent = result.error;
        confirmReviewButton.disabled = true;
        return;
      }
      $('wiringSqlResult').textContent =
        `${result.n_casos} caso(s) de ${dataset.nRows} fila(s).`;
      preview = {
        regla,
        estado: 'completado',
        descripcion: regla,
        tipo: 'manual',
        severidad: 'advertencia',
        campos_entrada: [],
        condicion_error: '',
        sql,
        trace,
        ...result,
      };
      confirmReviewButton.disabled = false;
    });
  }

  async function interpretRule(regla, comentario) {
    const trace = [];
    const response = await api.interpret({
      regla,
      tabla: revision.table_name,
      campos: fields,
      valoresEjemplo: dataset.sampleValues(fields.map((f) => f.nombre)),
      comentario,
    });
    (response.trace || []).forEach((step) => trace.push(step));

    if (response.estado !== 'completado' || !response.dqc) {
      return {
        regla,
        estado: response.estado || 'error',
        falta: response.falta,
        error: response.error,
        trace,
      };
    }

    const dqc = response.dqc;
    const result = executeOnData(dqc.sql, trace);
    if (!result.ok) {
      return { regla, estado: 'error', error: result.error, trace };
    }
    trace.push({ paso: 'resultado', estado: 'completado', n_casos: result.n_casos });

    let explicacion = '';
    if (result.n_casos > 0) {
      try {
        const answer = await api.explain({
          regla: dqc.descripcion || regla,
          condicion_error: dqc.condicion_error || '',
          columnas: result.columnas,
          ejemplos: result.ejemplos,
          n_casos: result.n_casos,
        });
        explicacion = [
          answer.explicacion,
          answer.factor_comun && `Factor común: ${answer.factor_comun}`,
          answer.posible_causa && `Causa probable: ${answer.posible_causa}`,
          answer.recomendacion && `Recomendación: ${answer.recomendacion}`,
        ]
          .filter(Boolean)
          .join('\n');
      } catch (_) {
        // explaining is a nicety; a control without it is still a control
      }
    }

    return { regla, estado: 'completado', ...dqc, ...result, explicacion, trace };
  }

  addRuleButton.addEventListener('click', async () => {
    const regla = $('newRule').value.trim();
    if (!regla)
      return leftMessage('Escribe una regla antes de iniciar la revisión.', true);
    if (!dataset) return leftMessage('Carga primero la tabla de datos.', true);

    $('reviewComment').value = '';
    if (!hasApi()) {
      askForQuery(regla);
      $('ruleReviewModal').style.display = 'flex';
      return;
    }

    leftMessage('Interpretando la regla…', false);
    addRuleButton.disabled = true;
    try {
      showPreview(await interpretRule(regla, ''));
      $('ruleReviewModal').style.display = 'flex';
      leftMessage('', false);
    } catch (err) {
      leftMessage(err.message, true);
    } finally {
      addRuleButton.disabled = false;
    }
  });

  reejecutarReviewButton.addEventListener('click', async () => {
    if (!hasApi()) return;
    const regla = $('newRule').value.trim();
    reejecutarReviewButton.disabled = true;
    $('reviewInterpretation').textContent = 'Reinterpretando con tu comentario…';
    try {
      showPreview(await interpretRule(regla, $('reviewComment').value.trim()));
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
      const saved = await store.createCheck(revision.revision_id, {
        regla: preview.regla,
        descripcion: preview.descripcion || preview.regla,
        tipo: preview.tipo || '',
        severidad: preview.severidad || '',
        campos_entrada: preview.campos_entrada || [],
        condicion_error: preview.condicion_error || '',
        sql: preview.sql,
        n_casos: preview.n_casos,
        columnas: preview.columnas || [],
        ejemplos: preview.ejemplos || [],
        explicacion: preview.explicacion || '',
        trace: preview.trace || [],
        feedback: $('reviewComment').value.trim(),
      });
      revision = await store.updateRevision(revision.revision_id, {
        status: 'completada',
      });
      $('ruleReviewModal').style.display = 'none';
      $('newRule').value = '';
      await loadRules(saved.check_id);
      leftMessage('Regla añadida.', false);
    } catch (err) {
      $('ruleReviewModal').style.display = 'none';
      leftMessage(err.message, true);
    } finally {
      confirmReviewButton.disabled = false;
    }
  });

  // ── a rules file: one rule after another, same path
  uploadRulesFileButton.addEventListener('click', async () => {
    const file = $('rulesFile').files[0];
    if (!file) return leftMessage('Selecciona un fichero de reglas.', true);
    if (!hasApi()) {
      return leftMessage(
        'Cargar un fichero de reglas necesita el modelo: sin API cada consulta se escribe a mano.',
        true,
      );
    }

    const text = await readFileText(file);
    const lines = text
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);
    uploadRulesFileButton.disabled = true;
    let saved = 0;
    let failed = 0;
    try {
      for (let i = 0; i < lines.length; i += 1) {
        leftMessage(`Regla ${i + 1} de ${lines.length}…`, false);
        try {
          const outcome = await interpretRule(lines[i], '');
          if (outcome.estado !== 'completado') {
            failed += 1;
            continue;
          }
          await store.createCheck(revision.revision_id, {
            regla: outcome.regla,
            descripcion: outcome.descripcion || outcome.regla,
            tipo: outcome.tipo || '',
            severidad: outcome.severidad || '',
            campos_entrada: outcome.campos_entrada || [],
            condicion_error: outcome.condicion_error || '',
            sql: outcome.sql,
            n_casos: outcome.n_casos,
            columnas: outcome.columnas || [],
            ejemplos: outcome.ejemplos || [],
            explicacion: outcome.explicacion || '',
            trace: outcome.trace || [],
          });
          saved += 1;
        } catch (_) {
          failed += 1;
        }
      }
      await loadRules();
      leftMessage(
        `${saved} regla(s) añadidas` + (failed ? `, ${failed} sin resultado.` : '.'),
        failed > 0 && saved === 0,
      );
    } finally {
      uploadRulesFileButton.disabled = false;
    }
  });

  // ── review decisions
  async function setStatus(status) {
    try {
      await store.updateCheck(revision.revision_id, selectedId, { status });
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
    await store.updateCheck(revision.revision_id, selectedId, { feedback });
    await loadRules(selectedId);
  });

  /** Re-run: with a model, re-derive the query with the reviewer's reason
      as the correction; without one, just run the stored query again. */
  reejecutarButton.addEventListener('click', async () => {
    const rule = current();
    const motivo = $('reejecutarReason').value.trim();
    if (!rule) return;
    if (!motivo)
      return leftMessage('Explica por qué quieres reejecutar la regla.', true);

    reejecutarButton.disabled = true;
    leftMessage('Reejecutando el control…', false);
    try {
      let patch;
      if (hasApi()) {
        const outcome = await interpretRule(rule.regla, motivo);
        if (outcome.estado !== 'completado') {
          throw new Error(outcome.falta || outcome.error || 'sin resultado');
        }
        patch = {
          descripcion: outcome.descripcion,
          tipo: outcome.tipo,
          severidad: outcome.severidad,
          campos_entrada: outcome.campos_entrada || [],
          condicion_error: outcome.condicion_error || '',
          sql: outcome.sql,
          n_casos: outcome.n_casos,
          columnas: outcome.columnas,
          ejemplos: outcome.ejemplos,
          explicacion: outcome.explicacion || '',
          trace: outcome.trace,
          feedback: motivo,
        };
      } else {
        const trace = [];
        const result = executeOnData(rule.sql, trace);
        if (!result.ok) throw new Error(result.error);
        patch = { ...result, trace, feedback: motivo };
      }
      await store.updateCheck(revision.revision_id, rule.check_id, patch);
      $('reejecutarReason').value = '';
      await loadRules(rule.check_id);
      leftMessage('Control reejecutado con tu corrección.', false);
    } catch (err) {
      leftMessage(err.message, true);
    } finally {
      reejecutarButton.disabled = false;
    }
  });

  // ── report
  generateReportButton.addEventListener('click', () => {
    const validated = rules.filter((r) => r.status === 'validated');
    const pending = rules.filter((r) => r.status === 'pending').length;
    const rejected = rules.filter((r) => r.status === 'rejected').length;

    // the centralised query: every validated control in one result set
    const sql = validated.length
      ? validated
          .map(
            (check) =>
              `SELECT '${String(check.check_id).replace(/'/g, "''")}' AS check_id, ` +
              `'${String(check.descripcion || check.regla).replace(/'/g, "''")}' AS control, ` +
              `'${String(check.severidad || '').replace(/'/g, "''")}' AS severidad, * ` +
              `FROM (${String(check.sql).trim().replace(/;+$/, '')})`,
          )
          .join('\nUNION ALL\n')
      : null;

    const rows = validated
      .map(
        (check) => `<tr>
          <td>${escapeHtml(check.descripcion || check.regla)}</td>
          <td>${escapeHtml(check.severidad || '–')}</td>
          <td>${check.n_casos === null || check.n_casos === undefined ? '–' : check.n_casos}</td>
        </tr>`,
      )
      .join('');

    $('wiringReportBody').innerHTML = `
      <div class="detail-box-modal">
        <div class="detail-label-modal">Estado de la revisión</div>
        <div class="wiring-grid">
          <div><strong>Validadas</strong><br/>${validated.length}</div>
          <div><strong>Pendientes</strong><br/>${pending}</div>
          <div><strong>Rechazadas</strong><br/>${rejected}</div>
          <div><strong>Filas analizadas</strong><br/>${revision.data_rows}</div>
        </div>
        ${pending ? '<div class="detail-metrics-modal">Hay reglas pendientes de revisar: el informe solo incluye las validadas.</div>' : ''}
      </div>
      <div class="detail-box-modal">
        <div class="detail-label-modal">Controles validados</div>
        ${
          rows
            ? `<table><thead><tr><th>Control</th><th>Severidad</th><th>Casos</th></tr></thead><tbody>${rows}</tbody></table>`
            : '<div class="detail-metrics-modal">Ninguna regla validada todavía. Valida al menos una para incluirla en el informe.</div>'
        }
      </div>
      ${
        sql
          ? `<div class="detail-box-modal">
               <div class="detail-label-modal">Consulta centralizada</div>
               <pre class="wiring-sql">${escapeHtml(sql)}</pre>
               <div class="modal-actions"><button id="wiringDownloadSql">Descargar .sql</button></div>
             </div>`
          : ''
      }`;
    reportModal.style.display = 'flex';

    if (sql) {
      $('wiringDownloadSql').addEventListener('click', () => {
        const blob = new Blob([sql], { type: 'application/sql' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `informe_${String(revision.name).replace(/\W+/g, '_').toLowerCase()}.sql`;
        link.click();
        URL.revokeObjectURL(link.href);
      });
    }
  });

  // ── list interactions
  rulesList.addEventListener('click', async (e) => {
    const item = e.target.closest('.rule-item');
    if (!item) return;
    if (e.target.matches('.rule-delete')) {
      const rule = rules.find((r) => r.check_id === item.dataset.id);
      if (!window.confirm(`Eliminar la regla "${rule.descripcion || rule.regla}"?`))
        return;
      await store.deleteCheck(revision.revision_id, rule.check_id);
      if (selectedId === rule.check_id) selectedId = null;
      await loadRules();
      return;
    }
    select(item.dataset.id);
  });

  async function start() {
    renderHeader();
    await loadRules();
  }

  try {
    if (await loadContext()) await start();
  } catch (err) {
    leftMessage(err.message, true);
  }
}
