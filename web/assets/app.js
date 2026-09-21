/* Which page is this, and who wires it.
 *
 * A classic <script src>, not a module, because the pages carry the line
 * the designs were handed back with and nothing more. Static imports would
 * need type="module" in the HTML; dynamic import() works from here and
 * costs the pages nothing.
 *
 * Everything lives inside an IIFE for the same reason. A classic script
 * shares the global scope with the demo script each mockup carries, and
 * that one already declares names like `escapeHtml` — declaring them again
 * out here throws before a single line runs. A module would have had its
 * own scope; this is what that costs.
 *
 * Step 3 (rules) runs against your API and SQLite in the browser — see
 * docs/API_CONTRACT.md and assets/pages/rules.js.
 *
 * The other three screens still talk to the Python backend under /dqc/*.
 * They are next in line; until then, they need that backend running and
 * step 3 does not.
 */

(function () {
  // Captured synchronously: after the first await, document.currentScript is
  // null, and the module paths have to resolve against THIS file rather than
  // against whichever page loaded it.
  // still inside the synchronous run, so currentScript is set
  const HERE = document.currentScript.src;
  const load = (path) => import(new URL(path, HERE).href);

  let $, escapeHtml, formatDate, fresh, hideMissingLogo, injectStyles, param;

  // ── the not-yet-migrated screens talk to the old backend ─────────────────────

  const API = '';

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

  function requireRevision() {
    const rev = param('rev');
    if (!rev) window.location.href = 'home.html';
    return rev;
  }

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

  // ── routing ──────────────────────────────────────────────────────────────────

  (async function wire() {
    ({ $, escapeHtml, formatDate, fresh, hideMissingLogo, injectStyles, param } =
      await load('./lib/dom.js'));

    hideMissingLogo();

    if ($('rulesList')) {
      const { initRules } = await load('./pages/rules.js');
      await initRules();
    } else if ($('createRevisionForm')) initNewRevision();
    else if ($('dictionaryForm')) initDictionary();
    else if (document.querySelector('.search-box input')) initHome();
  })();
})();
