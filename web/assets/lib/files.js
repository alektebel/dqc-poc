/* The uploaded CSVs, kept in the browser between screens.
 *
 * The files never leave the machine — the API only ever receives the
 * dictionary's field names, never the data. So step 1 has to leave the CSV
 * somewhere step 3 can read it, and that somewhere is IndexedDB:
 * localStorage is a string store with a ~5 MB budget, which a real extract
 * blows past immediately.
 *
 * The obvious consequence, and it is worth saying out loud in the UI:
 * open the same revision on another machine and its rules and results are
 * there, but the file is not. Re-running needs the file again.
 */

const DB_NAME = 'dqc-files';
const STORE = 'files';

function open() {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(new Error('No se pudo abrir el almacén local del navegador.'));
  });
}

function transact(mode, run) {
  return open().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const request = run(tx.objectStore(STORE));
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
        tx.oncomplete = () => db.close();
      }),
  );
}

const key = (revisionId, kind) => `${revisionId}:${kind}`;

/** Store a file's text. `kind` is 'data' or 'dictionary'. */
export function putFile(revisionId, kind, { filename, text }) {
  return transact('readwrite', (store) =>
    store.put(
      { filename, text, saved_at: new Date().toISOString() },
      key(revisionId, kind),
    ),
  );
}

/** Returns {filename, text} or null when this browser never saw the file. */
export function getFile(revisionId, kind) {
  return transact('readonly', (store) => store.get(key(revisionId, kind))).then(
    (value) => value || null,
  );
}

export async function deleteFiles(revisionId) {
  await transact('readwrite', (store) => store.delete(key(revisionId, 'data')));
  await transact('readwrite', (store) => store.delete(key(revisionId, 'dictionary')));
}
