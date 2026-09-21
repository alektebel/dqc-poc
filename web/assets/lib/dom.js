/* Reaching into the mockups without editing them. */

export const $ = (id) => document.getElementById(id);

export function param(name) {
  return new URLSearchParams(window.location.search).get(name) || '';
}

export function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function formatDate(iso) {
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
    Each mockup ships a demo script that has already attached handlers and
    kept no reference to them; this is how they are discarded without
    touching the HTML that registered them. */
export function fresh(node) {
  if (!node) return null;
  const clone = node.cloneNode(true);
  node.replaceWith(clone);
  return clone;
}

export function freshAll(selector) {
  return Array.from(document.querySelectorAll(selector)).map(fresh);
}

/** Style rules the wiring needs and the designs do not define. */
export function injectStyles(css) {
  const style = document.createElement('style');
  style.dataset.source = 'wiring';
  style.textContent = css;
  document.head.appendChild(style);
}

/** The designs reference pwc-logo.png, which this repo does not ship. */
export function hideMissingLogo() {
  document.querySelectorAll('.logo img').forEach((img) => {
    const hide = () => {
      img.style.visibility = 'hidden';
    };
    img.addEventListener('error', hide);
    if (img.complete && img.naturalWidth === 0) hide();
  });
}
