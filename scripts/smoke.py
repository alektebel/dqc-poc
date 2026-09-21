#!/usr/bin/env python3
"""Check that a running deployment actually works.

Not a liveness probe: it walks the flow the app exists for — create a
revision from a CSV, attach its dictionary, read the rules back, and
clean up after itself — plus every page and asset the browser needs. An
image that starts but forgot to copy ``web/`` passes a health check and
fails this.

Uses only the standard library, so it runs against a container from a CI
runner with nothing installed:

    python scripts/smoke.py                          # http://localhost:8000
    python scripts/smoke.py --base-url http://host:8000 --timeout 60

Exit code 0 when every check passes, 1 otherwise. It leaves no data
behind: the revision it creates is deleted at the end (and on failure,
best-effort).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

DATA_CSV = (
    "ID_CONTRATO;EDAD_CLIENTE;FECHA_CONCESION\n"
    "CT-1;140;2020-05-12\n"
    "CT-2;44;2019-11-03\n"
).encode()

DICT_CSV = (
    "Campo,Tipo,Descripcion\n"
    "ID_CONTRATO,TEXT,Identificador del contrato\n"
    "EDAD_CLIENTE,INTEGER,Edad del cliente en anios\n"
    "FECHA_CONCESION,DATE,Fecha de concesion\n"
).encode()

DESCRIPTION = (
    "Tabla de contratos hipotecarios con granularidad de contrato usada por "
    "la verificacion de despliegue. La clave primaria es ID_CONTRATO y "
    "contiene la edad del cliente y la fecha de concesion."
)

PAGES = ["home.html", "index.html", "dictionary.html", "rules.html",
         "assets/api.js", "assets/rules.js"]

_failures: list[str] = []


# ── tiny HTTP layer (stdlib only) ────────────────────────────────────────────

def _request(url: str, *, method: str = "GET", data: bytes | None = None,
             content_type: str | None = None, timeout: float = 30.0):
    req = urllib.request.Request(url, data=data, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers


def _multipart(fields: dict[str, str],
               files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    """Build a multipart/form-data body without pulling in requests."""
    boundary = f"----smoke{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode())
    for name, (filename, payload, ctype) in files.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n".encode())
        parts.append(payload)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# ── reporting ────────────────────────────────────────────────────────────────

def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'OK  ' if ok else 'FALLO'}  {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(label)
    return ok


def wait_for(base_url: str, timeout: float) -> bool:
    """Poll /health until the app answers — a container needs a moment."""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            status, body, _ = _request(f"{base_url}/health", timeout=5)
            if status == 200:
                backend = json.loads(body).get("llm_backend", "?")
                return check("la aplicación responde", True,
                             f"backend LLM: {backend}")
            last = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 — it is simply not up yet
            last = exc.__class__.__name__
        time.sleep(1)
    return check("la aplicación responde", False,
                 f"sin respuesta en {timeout:.0f}s ({last})")


# ── the checks ───────────────────────────────────────────────────────────────

def check_pages(base_url: str) -> None:
    status, _, headers = _request(f"{base_url}/", timeout=10)
    # urllib follows the redirect, so a 200 here means / led somewhere real
    check("/ sirve la aplicación", status == 200, f"HTTP {status}")
    for page in PAGES:
        status, body, _ = _request(f"{base_url}/app/{page}", timeout=10)
        check(f"/app/{page}", status == 200 and len(body) > 0,
              f"HTTP {status}, {len(body)} bytes")


def check_flow(base_url: str) -> None:
    """Create a revision, attach a dictionary, read it back, delete it."""
    body, ctype = _multipart(
        {"name": f"smoke {uuid.uuid4().hex[:6]}", "description": DESCRIPTION,
         "table_name": "contratos"},
        {"data_file": ("contratos.csv", DATA_CSV, "text/csv")})
    status, payload, _ = _request(f"{base_url}/dqc/revisions", method="POST",
                                  data=body, content_type=ctype)
    if not check("crear revisión desde un CSV", status == 201,
                 f"HTTP {status}: {payload[:160].decode(errors='replace')}"):
        return
    revision = json.loads(payload)
    rid = revision["revision_id"]
    check("el CSV se interpretó", revision["data_rows"] == 2
          and revision["data_columns"] == 3,
          f"{revision['data_rows']} filas, {revision['data_columns']} columnas")

    try:
        body, ctype = _multipart(
            {}, {"dictionary": ("dicc.csv", DICT_CSV, "text/csv")})
        status, payload, _ = _request(
            f"{base_url}/dqc/revisions/{rid}/dictionary", method="POST",
            data=body, content_type=ctype)
        ok = status == 200
        fields = json.loads(payload).get("dictionary_fields") if ok else None
        check("subir el diccionario", ok and fields == 3,
              f"HTTP {status}, {fields} campos")

        status, payload, _ = _request(f"{base_url}/dqc/revisions/{rid}/rules")
        check("listar las reglas de la revisión",
              status == 200 and json.loads(payload)["rules_total"] == 0,
              f"HTTP {status}")

        status, payload, _ = _request(f"{base_url}/dqc/revisions/{rid}/report")
        check("generar el informe", status == 200, f"HTTP {status}")
    finally:
        status, _, _ = _request(f"{base_url}/dqc/revisions/{rid}",
                                method="DELETE")
        check("borrar la revisión de prueba", status == 200, f"HTTP {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="segundos de espera a que la aplicación arranque")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"Verificando {base_url}")
    if not wait_for(base_url, args.timeout):
        print("\nLa aplicación no arrancó. Nada más que comprobar.")
        return 1

    print("\nPantallas y recursos:")
    check_pages(base_url)
    print("\nFlujo de la API:")
    check_flow(base_url)

    print()
    if _failures:
        print(f"FALLA: {len(_failures)} comprobación(es) — "
              + ", ".join(_failures))
        return 1
    print("Todo correcto: el despliegue sirve las pantallas y el flujo responde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
