#!/usr/bin/env python
"""Can we actually send a query to a SAS server? — an interactive feasibility probe.

The DQC generator emits SAS/SQL but nothing in this repo has ever connected to
a SAS server: validation runs statically, and dynamic validation runs against a
local SQLite fixture. Before designing anything that submits generated code to
a real server, the failure surface has to be known — which failures are
retryable, which are configuration, which mean "stop and call someone".

This probe walks the connection path in stages and reports a machine-readable
code for every outcome, so the result can be pasted into a ticket or fed to a
retry policy. It is **read-only by default**: the only code it submits is a
`PROC SQL` SELECT against a table you name, plus harmless `%PUT` statements.
Nothing is created, dropped or updated unless you pass --allow-write.

    python scripts/sas_probe.py --dry-run          # no network: list the checks
    python scripts/sas_probe.py --host sas.corp --port 8591 --user me
    python scripts/sas_probe.py --viya https://viya.corp --token "$TOKEN"
    python scripts/sas_probe.py --json > sas_probe.json

Stages: dependency → config → TCP reachability → TLS → authentication →
session start → trivial submit → dictionary read → target table → SQL dialect.
Each stage only runs if the previous one passed, because a failure downstream
of a broken connection tells you nothing.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import socket
import ssl
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── outcome codes ─────────────────────────────────────────────────────────
# Stable identifiers so a caller can branch on them. The `retryable` flag is
# the operational question: does waiting and trying again have any chance?

CODES: dict[str, tuple[str, bool, str]] = {
    # code                     (stage,          retryable, meaning)
    "OK":                      ("-",            False, "stage succeeded"),
    "SKIPPED":                 ("-",            False, "not attempted (earlier stage failed)"),

    "DEP_MISSING":             ("dependency",   False, "saspy / requests not installed"),
    "DEP_JAVA_MISSING":        ("dependency",   False, "IOM access needs a Java runtime on PATH"),

    "CFG_INCOMPLETE":          ("config",       False, "host/port/auth not supplied"),
    "CFG_NO_SASCFG":           ("config",       False, "saspy has no sascfg_personal.py to read"),

    "NET_DNS":                 ("tcp",          False, "hostname does not resolve"),
    "NET_REFUSED":             ("tcp",          True,  "nothing listening on that port"),
    "NET_TIMEOUT":             ("tcp",          True,  "no response — firewall drop or server busy"),
    "NET_UNREACHABLE":         ("tcp",          True,  "no route to host"),

    "TLS_HANDSHAKE":           ("tls",          False, "TLS negotiation failed"),
    "TLS_CERT_UNTRUSTED":      ("tls",          False, "certificate not trusted — corporate CA missing"),
    "TLS_HOSTNAME_MISMATCH":   ("tls",          False, "certificate does not match the hostname"),
    "TLS_EXPIRED":             ("tls",          False, "certificate expired"),

    "AUTH_INVALID":            ("auth",         False, "credentials rejected"),
    "AUTH_EXPIRED":            ("auth",         True,  "token expired — refresh and retry"),
    "AUTH_LOCKED":             ("auth",         False, "account locked or disabled"),
    "AUTH_MFA_REQUIRED":       ("auth",         False, "interactive second factor needed"),

    "SESS_NO_LICENSE":         ("session",      False, "no SAS licence seat available"),
    "SESS_QUOTA":              ("session",      True,  "concurrent-session limit reached"),
    "SESS_LAUNCH_FAILED":      ("session",      True,  "workspace server would not start"),
    "SESS_TIMEOUT":            ("session",      True,  "session start timed out"),

    "SUBMIT_SYNTAX":           ("submit",       False, "SAS rejected the code (ERROR: in the log)"),
    "SUBMIT_AUTHZ":            ("submit",       False, "not authorised to run this"),
    "SUBMIT_TIMEOUT":          ("submit",       True,  "statement exceeded the time budget"),
    "SUBMIT_DISCONNECTED":     ("submit",       True,  "session dropped mid-statement"),

    "LIB_NOT_ASSIGNED":        ("library",      False, "libref does not exist or is not assigned"),
    "LIB_NO_ACCESS":           ("library",      False, "no read permission on the library"),

    "TABLE_NOT_FOUND":         ("table",        False, "table does not exist in that library"),
    "TABLE_NO_ACCESS":         ("table",        False, "no read permission on the table"),
    "TABLE_LOCKED":            ("table",        True,  "table locked by another process"),

    "SQL_DIALECT":             ("dialect",      False, "PROC SQL rejected a construct the generator emits"),

    "ENDPOINT_NOT_VIYA":       ("auth",         False, "reachable, but not a Viya API (no identities endpoint)"),
    "UNKNOWN":                 ("-",            False, "unclassified — see detail"),
}


@dataclass
class Result:
    stage: str
    code: str
    detail: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.code == "OK"

    @property
    def retryable(self) -> bool:
        return CODES.get(self.code, ("-", False, ""))[1]

    def to_dict(self) -> dict:
        return {"stage": self.stage, "code": self.code, "ok": self.ok,
                "retryable": self.retryable, "detail": self.detail,
                "elapsed_ms": self.elapsed_ms,
                "meaning": CODES.get(self.code, ("-", False, "unknown"))[2]}


@dataclass
class Probe:
    results: list[Result] = field(default_factory=list)

    def add(self, stage: str, code: str, detail: str = "", elapsed_ms: int = 0) -> Result:
        r = Result(stage, code, detail, elapsed_ms)
        self.results.append(r)
        return r

    def skip_rest(self, stages: list[str], why: str) -> None:
        for s in stages:
            self.add(s, "SKIPPED", why)

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if not r.ok and r.code != "SKIPPED"]


# ── classification ────────────────────────────────────────────────────────

def classify_socket_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, socket.gaierror):
        return "NET_DNS", str(exc)
    if isinstance(exc, socket.timeout) or isinstance(exc, TimeoutError):
        return "NET_TIMEOUT", "no response before the timeout"
    if isinstance(exc, ConnectionRefusedError):
        return "NET_REFUSED", str(exc)
    # errno values differ per platform, and Windows reports WSA codes — 10051
    # ENETUNREACH / 10065 EHOSTUNREACH — which the symbolic constants do not
    # cover, so both are checked.
    if isinstance(exc, OSError):
        codes = {getattr(exc, "errno", None), getattr(exc, "winerror", None)}
        if codes & {errno.ENETUNREACH, errno.EHOSTUNREACH, 101, 113, 51, 65,
                    10051, 10065}:
            return "NET_UNREACHABLE", str(exc)
    return "UNKNOWN", f"{type(exc).__name__}: {exc}"


def classify_tls_error(exc: Exception) -> tuple[str, str]:
    text = str(exc).lower()
    if isinstance(exc, ssl.SSLCertVerificationError) or "certificate verify failed" in text:
        if "expired" in text:
            return "TLS_EXPIRED", str(exc)
        if "hostname mismatch" in text or "doesn't match" in text:
            return "TLS_HOSTNAME_MISMATCH", str(exc)
        return "TLS_CERT_UNTRUSTED", str(exc)
    return "TLS_HANDSHAKE", f"{type(exc).__name__}: {exc}"


def classify_sas_log(log: str) -> tuple[str, str]:
    """Map a SAS log to a code. SAS reports failures in the log, often with a
    200-level HTTP status, so the log is the authority, not the return code."""
    low = (log or "").lower()
    checks = [
        ("is not assigned", "LIB_NOT_ASSIGNED"),
        ("libref", "LIB_NOT_ASSIGNED"),
        ("user does not have appropriate authorization", "TABLE_NO_ACCESS"),
        ("insufficient authorization", "TABLE_NO_ACCESS"),
        ("file .* does not exist", "TABLE_NOT_FOUND"),
        ("does not exist", "TABLE_NOT_FOUND"),
        ("is in use by another", "TABLE_LOCKED"),
        ("lock held by", "TABLE_LOCKED"),
        ("syntax error", "SUBMIT_SYNTAX"),
        ("statement is not valid", "SQL_DIALECT"),
        ("function .* is unknown", "SQL_DIALECT"),
    ]
    import re as _re
    for pattern, code in checks:
        if _re.search(pattern, low):
            return code, _first_error_line(log)
    if "error:" in low:
        return "SUBMIT_SYNTAX", _first_error_line(log)
    return "OK", ""


def _first_error_line(log: str) -> str:
    for line in (log or "").splitlines():
        if line.strip().upper().startswith("ERROR"):
            return line.strip()[:200]
    return (log or "")[:200]


def classify_http_status(status: int, body: str = "", stage: str = "") -> tuple[str, str]:
    """Viya REST failures. Stage-aware: a 404 during authentication means the
    host is not a Viya API, not that some table is missing."""
    low = body.lower()
    if status == 404 and stage == "auth":
        return "ENDPOINT_NOT_VIYA", body[:200]
    if status in (401,):
        if "expired" in low:
            return "AUTH_EXPIRED", body[:200]
        if "mfa" in low or "second factor" in low:
            return "AUTH_MFA_REQUIRED", body[:200]
        return "AUTH_INVALID", body[:200]
    if status == 403:
        return "AUTH_LOCKED" if "locked" in low else "SUBMIT_AUTHZ", body[:200]
    if status == 404:
        return "TABLE_NOT_FOUND", body[:200]
    if status == 409:
        return "SESS_QUOTA", body[:200]
    if status == 429:
        return "SESS_QUOTA", body[:200]
    if status in (502, 503, 504):
        return "SESS_LAUNCH_FAILED", body[:200]
    if status >= 400:
        return "UNKNOWN", f"HTTP {status}: {body[:200]}"
    return "OK", ""


# ── stages ────────────────────────────────────────────────────────────────

def stage_dependency(probe: Probe, mode: str) -> bool:
    t = time.time()
    if mode == "viya":
        try:
            import httpx  # noqa: F401
        except ImportError:
            probe.add("dependency", "DEP_MISSING", "httpx is required for Viya REST")
            return False
        probe.add("dependency", "OK", "httpx available",
                  int((time.time() - t) * 1000))
        return True
    try:
        import saspy  # noqa: F401
    except ImportError:
        probe.add("dependency", "DEP_MISSING",
                  "pip install saspy  (IOM/STP access to SAS 9.4)")
        return False
    import shutil
    if not shutil.which("java"):
        probe.add("dependency", "DEP_JAVA_MISSING",
                  "saspy IOM needs a JRE on PATH")
        return False
    probe.add("dependency", "OK", "saspy + java available",
              int((time.time() - t) * 1000))
    return True


def stage_tcp(probe: Probe, host: str, port: int, timeout: float) -> bool:
    t = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except Exception as exc:  # noqa: BLE001 — every failure is classified
        code, detail = classify_socket_error(exc)
        probe.add("tcp", code, detail, int((time.time() - t) * 1000))
        return False
    probe.add("tcp", "OK", f"{host}:{port} reachable", int((time.time() - t) * 1000))
    return True


def stage_tls(probe: Probe, host: str, port: int, timeout: float, verify: bool) -> bool:
    t = time.time()
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cipher = tls.cipher()
        probe.add("tls", "OK", f"{cipher[1] if cipher else 'negotiated'}"
                  + ("" if verify else "  (verification DISABLED)"),
                  int((time.time() - t) * 1000))
        return True
    except Exception as exc:  # noqa: BLE001
        code, detail = classify_tls_error(exc)
        probe.add("tls", code, detail, int((time.time() - t) * 1000))
        return False


def stage_viya(probe: Probe, base: str, token: str, table: str,
               timeout: float, verify: bool) -> None:
    import httpx
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    t = time.time()
    try:
        with httpx.Client(timeout=timeout, verify=verify) as client:
            r = client.get(f"{base.rstrip('/')}/identities/users/@currentUser",
                           headers=headers)
        code, detail = classify_http_status(r.status_code, r.text, stage="auth")
        probe.add("auth", code, detail or f"HTTP {r.status_code}",
                  int((time.time() - t) * 1000))
        if code != "OK":
            probe.skip_rest(["session", "submit", "library", "table", "dialect"],
                            "authentication failed")
            return
    except Exception as exc:  # noqa: BLE001
        probe.add("auth", "UNKNOWN", f"{type(exc).__name__}: {exc}")
        probe.skip_rest(["session", "submit", "library", "table", "dialect"],
                        "authentication raised")
        return
    probe.skip_rest(["session", "submit", "library", "table", "dialect"],
                    "Viya compute-session probing not implemented — "
                    "authentication verified only")


def stage_saspy(probe: Probe, cfgname: str, host: str, port: int, user: str,
                password: str, table: str, allow_write: bool, timeout: float) -> None:
    import saspy
    t = time.time()
    session = None
    try:
        kwargs = {"cfgname": cfgname} if cfgname else {}
        if host:
            kwargs.update({"iomhost": host, "iomport": port})
        if user:
            kwargs.update({"omruser": user, "omrpw": password})
        session = saspy.SASsession(**kwargs)
        probe.add("session", "OK", str(session)[:120], int((time.time() - t) * 1000))
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if "authentic" in text or "password" in text:
            code = "AUTH_INVALID"
        elif "licens" in text:
            code = "SESS_NO_LICENSE"
        elif "timed out" in text:
            code = "SESS_TIMEOUT"
        else:
            code = "SESS_LAUNCH_FAILED"
        probe.add("session", code, f"{type(exc).__name__}: {exc}"[:200],
                  int((time.time() - t) * 1000))
        probe.skip_rest(["submit", "library", "table", "dialect"],
                        "no session")
        return

    def submit(stage: str, code_text: str) -> str | None:
        t0 = time.time()
        try:
            out = session.submit(code_text)
        except Exception as exc:  # noqa: BLE001
            probe.add(stage, "SUBMIT_DISCONNECTED", f"{type(exc).__name__}: {exc}"[:200],
                      int((time.time() - t0) * 1000))
            return None
        log = out.get("LOG", "")
        code_, detail = classify_sas_log(log)
        probe.add(stage, code_, detail, int((time.time() - t0) * 1000))
        return log if code_ == "OK" else None

    try:
        if submit("submit", "%put PROBE_OK;") is None:
            probe.skip_rest(["library", "table", "dialect"], "trivial submit failed")
            return

        libref = table.split(".")[0] if "." in table else "WORK"
        if submit("library", f"proc sql noprint; select count(*) into :n from "
                             f"dictionary.libnames where libname=upcase('{libref}'); quit;") is None:
            probe.skip_rest(["table", "dialect"], "library not readable")
            return

        if submit("table", f"proc sql outobs=1; select * from {table}; quit;") is None:
            probe.skip_rest(["dialect"], "target table not readable")
            return

        # Constructs the generator actually emits — this is the question that
        # matters for feasibility, not whether the server is up.
        dialect = (f"proc sql outobs=1; select count(*) as n, "
                   f"sum(case when 1=1 then 1 else 0 end) as c "
                   f"from {table} having calculated n >= 0; quit;")
        submit("dialect", dialect)

        if allow_write:
            submit("write", "data work._probe_; x=1; run;")
    finally:
        try:
            session.endsas()
        except Exception:  # noqa: BLE001
            pass


# ── simulation ────────────────────────────────────────────────────────────
# A real SAS server is often unavailable long before the integration that
# depends on it needs writing — behind Citrix, licensed per seat, or simply
# owned by another team. --simulate replays any classified outcome so retry
# policy, error surfacing and operational runbooks can be exercised and tested
# without one.

# Which stages have already succeeded when a given stage fails.
_STAGE_ORDER = ["dependency", "config", "tcp", "tls", "auth", "session",
                "submit", "library", "table", "dialect"]
assert {v[0] for v in CODES.values()} <= set(_STAGE_ORDER) | {"-"}, \
    "every code's stage must be simulable"


def simulate(code: str) -> Probe:
    """Build the Probe a real run would produce if it failed with ``code``."""
    if code not in CODES:
        raise KeyError(code)
    probe = Probe()
    stage, _retry, _meaning = CODES[code]
    order = [st for st in _STAGE_ORDER if st != "config" or stage == "config"]
    if code == "OK":
        for st in order:
            probe.add(st, "OK", "simulated")
        return probe
    if stage == "-":
        stage = "submit"
    idx = order.index(stage)
    for st in order[:idx]:
        probe.add(st, "OK", "simulated")
    probe.add(stage, code, f"simulated {code}")
    for st in order[idx + 1:]:
        probe.add(st, "SKIPPED", f"simulated failure at {stage}")
    return probe


# ── reporting ─────────────────────────────────────────────────────────────

def print_report(probe: Probe) -> None:
    print()
    print(f"  {'stage':<12} {'code':<24} {'ms':>7}  detail")
    print("  " + "─" * 88)
    for r in probe.results:
        mark = "✓" if r.ok else ("·" if r.code == "SKIPPED" else "✗")
        flag = "  [retryable]" if r.retryable else ""
        print(f"{mark} {r.stage:<12} {r.code:<24} {r.elapsed_ms:>7}  {r.detail[:52]}{flag}")
    print()
    if not probe.failed:
        print("  FEASIBLE — every attempted stage passed.")
        return
    # Stages fail independently (a missing client *and* an unreachable host are
    # two separate tickets), so report all of them, not just the first.
    print(f"  BLOCKED — {len(probe.failed)} stage(s) failed:")
    for r in probe.failed:
        meaning = CODES.get(r.code, ("-", False, ""))[2]
        print(f"    {r.stage:<11} {r.code:<22} {meaning}")
    if any(r.retryable for r in probe.failed):
        retry = ", ".join(r.code for r in probe.failed if r.retryable)
        print(f"\n  Retry may help for: {retry}")
    hard = [r.code for r in probe.failed if not r.retryable]
    if hard:
        print(f"  Configuration or authorisation, retrying will not help: "
              f"{', '.join(hard)}")


def print_dry_run() -> None:
    print(__doc__)
    print(f"  {'code':<24} {'stage':<12} retryable  meaning")
    print("  " + "─" * 88)
    for code, (stage, retry, meaning) in CODES.items():
        if code in ("OK", "SKIPPED"):
            continue
        print(f"  {code:<24} {stage:<12} {'yes' if retry else 'no':<9}  {meaning}")
    print(f"\n  {len(CODES) - 2} classified failure modes across 9 stages.")
    print("  Nothing was sent — pass --host/--viya to probe a real server.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", help="SAS 9.4 IOM workspace server host")
    ap.add_argument("--port", type=int, default=8591, help="IOM port (default 8591)")
    ap.add_argument("--user", default=os.getenv("SAS_USER", ""))
    ap.add_argument("--password", default=os.getenv("SAS_PASSWORD", ""))
    ap.add_argument("--cfgname", default=os.getenv("SASPY_CFGNAME", ""),
                    help="saspy sascfg_personal.py entry")
    ap.add_argument("--viya", help="SAS Viya base URL (REST mode)")
    ap.add_argument("--token", default=os.getenv("SAS_TOKEN", ""))
    ap.add_argument("--table", default="mylib.ciclos_recuperacion",
                    help="table to attempt a 1-row SELECT against")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (diagnosing a corporate CA)")
    ap.add_argument("--allow-write", action="store_true",
                    help="also create a scratch WORK dataset (default: read-only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list the stages and failure codes, connect to nothing")
    ap.add_argument("--simulate", metavar="CODE",
                    help="replay a classified outcome (e.g. SESS_QUOTA, OK, "
                         "ALL) without a server, to exercise error handling")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.simulate:
        wanted = ([c for c in CODES if c not in ("OK", "SKIPPED")]
                  if args.simulate.upper() == "ALL" else [args.simulate])
        overall = 0
        for code in wanted:
            if code not in CODES:
                print(f"Unknown code {code!r}. Try --dry-run for the list.",
                      file=sys.stderr)
                return 2
            probe = simulate(code)
            if args.json:
                print(json.dumps({"simulated": code,
                                  "results": [r.to_dict() for r in probe.results],
                                  "feasible": not probe.failed}))
            else:
                print(f"\n══ simulating {code} "
                      f"{'─' * max(0, 60 - len(code))}")
                print_report(probe)
            overall |= 1 if probe.failed else 0
        return overall

    if args.dry_run or (not args.host and not args.viya):
        if not args.json:
            print_dry_run()
        else:
            print(json.dumps({"codes": {k: {"stage": v[0], "retryable": v[1],
                                            "meaning": v[2]}
                                        for k, v in CODES.items()}}, indent=2))
        return 0

    probe = Probe()
    mode = "viya" if args.viya else "iom"

    deps_ok = stage_dependency(probe, mode)

    if mode == "viya":
        from urllib.parse import urlparse
        u = urlparse(args.viya)
        host, port = u.hostname or "", u.port or (443 if u.scheme == "https" else 80)
    else:
        host, port = args.host, args.port

    # Network stages first and unconditionally: they need no SAS dependency,
    # and knowing the host is unreachable *as well as* the client being
    # missing saves a second round trip with the infrastructure team.
    net_ok = stage_tcp(probe, host, port, args.timeout)
    tls_ok = True
    if net_ok and mode == "viya" and u.scheme == "https":
        tls_ok = stage_tls(probe, host, port, args.timeout, not args.insecure)
    elif mode != "viya":
        probe.add("tls", "SKIPPED", "IOM negotiates its own transport")

    if not deps_ok:
        probe.skip_rest(["auth", "session", "submit", "library", "table", "dialect"],
                        "client dependency missing")
    elif not net_ok:
        probe.skip_rest(["auth", "session", "submit", "library", "table", "dialect"],
                        "host unreachable")
    elif not tls_ok:
        probe.skip_rest(["auth", "session", "submit", "library", "table", "dialect"],
                        "TLS failed")
    elif mode == "viya":
        stage_viya(probe, args.viya, args.token, args.table,
                   args.timeout, not args.insecure)
    else:
        probe.add("auth", "SKIPPED", "verified as part of session start")
        stage_saspy(probe, args.cfgname, args.host, args.port, args.user,
                    args.password, args.table, args.allow_write, args.timeout)

    if args.json:
        print(json.dumps({"results": [r.to_dict() for r in probe.results],
                          "feasible": not probe.failed}, indent=2))
    else:
        print_report(probe)
    return 0 if not probe.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
