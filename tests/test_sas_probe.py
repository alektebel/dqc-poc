"""SAS connectivity probe — failure classification.

The probe's value is the mapping from a raw error to an actionable code, so
that is what is tested. No SAS server is contacted.
"""
import socket
import ssl
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sas_probe as sp  # noqa: E402


# ── network ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc, expected", [
    (socket.gaierror("Name or service not known"), "NET_DNS"),
    (ConnectionRefusedError(111, "Connection refused"), "NET_REFUSED"),
    (socket.timeout("timed out"), "NET_TIMEOUT"),
    (TimeoutError("timed out"), "NET_TIMEOUT"),
])
def test_socket_errors_are_classified(exc, expected):
    assert sp.classify_socket_error(exc)[0] == expected


def test_dns_failure_is_not_retryable_but_a_closed_port_is():
    """A name that does not resolve will not start resolving; a port that is
    closed may open when the service restarts."""
    assert sp.CODES["NET_DNS"][1] is False
    assert sp.CODES["NET_REFUSED"][1] is True


# ── TLS ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg, expected", [
    ("certificate verify failed: certificate has expired", "TLS_EXPIRED"),
    ("certificate verify failed: Hostname mismatch", "TLS_HOSTNAME_MISMATCH"),
    ("certificate verify failed: unable to get local issuer certificate",
     "TLS_CERT_UNTRUSTED"),
])
def test_tls_errors_are_classified(msg, expected):
    assert sp.classify_tls_error(ssl.SSLCertVerificationError(msg))[0] == expected


def test_non_certificate_tls_error_falls_back_to_handshake():
    assert sp.classify_tls_error(ssl.SSLError("wrong version number"))[0] == "TLS_HANDSHAKE"


# ── SAS log ──────────────────────────────────────────────────────────────

def test_clean_log_is_ok():
    assert sp.classify_sas_log("NOTE: PROCEDURE SQL used 0.01 seconds.")[0] == "OK"


@pytest.mark.parametrize("log, expected", [
    ("ERROR: Libref MYLIB is not assigned.", "LIB_NOT_ASSIGNED"),
    ("ERROR: File MYLIB.NOPE.DATA does not exist.", "TABLE_NOT_FOUND"),
    ("ERROR: User does not have appropriate authorization level.", "TABLE_NO_ACCESS"),
    ("ERROR: The data set is in use by another process.", "TABLE_LOCKED"),
    ("ERROR 22-322: Syntax error, expecting one of the following.", "SUBMIT_SYNTAX"),
])
def test_sas_log_errors_are_classified(log, expected):
    code, detail = sp.classify_sas_log(log)
    assert code == expected
    assert detail.startswith("ERROR")


def test_sas_reports_failure_in_the_log_not_the_return_code():
    """SAS can return success while the log carries ERROR:, which is why the
    log is the authority here."""
    code, _ = sp.classify_sas_log("NOTE: fine\nERROR: Syntax error.\nNOTE: done")
    assert code != "OK"


# ── HTTP / Viya ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("status, body, expected", [
    (401, "invalid credentials", "AUTH_INVALID"),
    (401, "token has expired", "AUTH_EXPIRED"),
    (401, "mfa required", "AUTH_MFA_REQUIRED"),
    (403, "account is locked", "AUTH_LOCKED"),
    (403, "forbidden", "SUBMIT_AUTHZ"),
    (429, "too many requests", "SESS_QUOTA"),
    (503, "service unavailable", "SESS_LAUNCH_FAILED"),
])
def test_http_statuses_are_classified(status, body, expected):
    assert sp.classify_http_status(status, body)[0] == expected


def test_404_during_auth_means_not_a_viya_endpoint():
    """Stage awareness: a 404 while authenticating is a wrong base URL, not a
    missing table. Found by pointing the probe at a non-Viya HTTPS host."""
    assert sp.classify_http_status(404, "Not found.", stage="auth")[0] == "ENDPOINT_NOT_VIYA"
    assert sp.classify_http_status(404, "Not found.", stage="table")[0] == "TABLE_NOT_FOUND"


def test_expired_token_is_retryable_but_invalid_credentials_are_not():
    assert sp.CODES["AUTH_EXPIRED"][1] is True
    assert sp.CODES["AUTH_INVALID"][1] is False


# ── probe bookkeeping ────────────────────────────────────────────────────

def test_every_code_declares_a_stage_and_a_meaning():
    for code, (stage, retryable, meaning) in sp.CODES.items():
        assert stage and meaning, code
        assert isinstance(retryable, bool), code


def test_skipped_stages_are_not_counted_as_failures():
    probe = sp.Probe()
    probe.add("tcp", "OK")
    probe.skip_rest(["auth", "session"], "no client")
    assert probe.failed == []


def test_failed_collects_every_independent_failure():
    probe = sp.Probe()
    probe.add("dependency", "DEP_MISSING")
    probe.add("tcp", "NET_DNS")
    assert [r.code for r in probe.failed] == ["DEP_MISSING", "NET_DNS"]


# ── setup wizard ─────────────────────────────────────────────────────────

import sas_setup as ss  # noqa: E402


def test_profile_never_carries_a_password_field():
    """Passwords come from SAS_PASSWORD or a prompt; they must not be
    persistable, so the dataclass has no slot for one."""
    assert "password" not in ss.Profile().to_dict()
    assert "token" not in ss.Profile().to_dict()


def test_profiles_and_config_are_written_private(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ss, "PROFILES", tmp_path / "sas_profiles.json")
    monkeypatch.setattr(ss, "SASCFG", tmp_path / "sascfg_personal.py")
    p = ss.Profile(name="corp", host="sas.corp", port=8591, user="me")
    ss.save_profile(p)
    cfg = ss.write_sascfg(p)
    assert (tmp_path / "sas_profiles.json").stat().st_mode & 0o077 == 0
    assert cfg.stat().st_mode & 0o077 == 0


def test_generated_sascfg_is_the_module_saspy_expects(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ss, "SASCFG", tmp_path / "sascfg_personal.py")
    cfg = ss.write_sascfg(ss.Profile(name="corp", host="sas.corp", port=8591))
    ns: dict = {}
    exec(compile(cfg.read_text(), str(cfg), "exec"), ns)   # noqa: S102 - our own output
    assert ns["SAS_config_names"] == ["corp"]
    assert ns["corp"]["iomhost"] == "sas.corp"
    assert ns["corp"]["iomport"] == 8591


def test_round_trips_a_saved_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(ss, "PROFILES", tmp_path / "sas_profiles.json")
    ss.save_profile(ss.Profile(name="a", host="h1"))
    ss.save_profile(ss.Profile(name="b", host="h2"))
    saved = ss.load_profiles()
    assert saved["a"]["host"] == "h1" and saved["b"]["host"] == "h2"


def test_corrupt_profile_file_does_not_crash(tmp_path, monkeypatch):
    bad = tmp_path / "sas_profiles.json"
    bad.write_text("{not json")
    monkeypatch.setattr(ss, "PROFILES", bad)
    assert ss.load_profiles() == {}


def test_missing_dependencies_are_reported_as_install_commands():
    missing = ss.check_dependencies("iom")
    # saspy is not a dependency of this project, so this must be non-empty here
    assert any("saspy" in m for m in missing)
    assert all(m.startswith(("pip install", "install")) for m in missing)


def test_ask_takes_the_default_without_a_terminal(monkeypatch):
    """input() and getpass block forever under CI or a pipe; the wizard must
    fall through to defaults instead of hanging."""
    monkeypatch.setattr(ss.sys.stdin, "isatty", lambda: False)
    assert ss.ask("Host", "sas.corp") == "sas.corp"
    assert ss.ask("Host", "") == ""
