# Submitting generated DQCs to a SAS server — feasibility

Nothing in this repo has ever connected to a SAS server. The generator emits
SAS/`PROC SQL`, `dqc_react.static_validate` checks it without executing, and
dynamic validation runs against a local SQLite fixture. Before designing
anything that submits generated code to a real server, the failure surface has
to be known.

Two scripts, one that creates a connection and one that diagnoses it.

## Setting one up — `scripts/sas_setup.py`

```bash
python scripts/sas_setup.py                 # interactive wizard
python scripts/sas_setup.py --verify        # re-test the saved profile
python scripts/sas_setup.py --show          # print the config it would use
python scripts/sas_setup.py --non-interactive --host sas.corp --user me
```

It asks for what it needs, writes the config saspy expects, verifies it end to
end by invoking the probe, and leaves a reusable profile behind.

- Profiles in `~/.dqc/sas_profiles.json`, generated saspy config in
  `~/.dqc/sascfg_personal.py`, both `0600`.
- **Passwords are never written to either.** They come from `SAS_PASSWORD` or a
  prompt, per run. The `Profile` dataclass has no field for one, so there is
  nowhere for a secret to be persisted by accident.
- saspy is configured by a *Python module*, not a dotfile, which is why the
  config is generated rather than templated — and why the setup tells you to
  put `~/.dqc` on `PYTHONPATH`.
- It builds the Java classpath for you — see below.
- Prerequisites are reported as install commands, and the profile is saved
  anyway so it is ready once they are resolved.

### Installing a JRE

saspy's IOM access runs over Java, so a runtime has to be present before
anything else matters. **Version matters more than you would expect**: the SAS
9.4 client jars are old (log4j 1.2.x, `sas.core` 9.4) and are not tested
against current JDKs. Java **11** is the safe default, **8** the fallback if
IOM refuses to start.

| Platform | Command |
|---|---|
| Any, with `mise` | `mise use -g java@temurin-11` — no sudo |
| Arch / Omarchy | `sudo pacman -S jre11-openjdk` |
| Debian / Ubuntu | `sudo apt install openjdk-11-jre-headless` |
| Fedora / RHEL | `sudo dnf install java-11-openjdk-headless` |
| macOS | `brew install --cask temurin@11` |
| Windows | `winget install EclipseAdoptium.Temurin.11.JRE` |

**Do not install the unversioned distro package.** On Arch today
`jre-openjdk` is Java **26**, far newer than the SAS jars expect. The setup
script names the command for the package manager actually on the machine, and
warns when the `java` already on `PATH` is newer than 17 rather than letting it
fail later inside saspy.

```bash
java -version     # confirm afterwards
```

### The Java classpath

saspy's IOM access method runs over Java and needs **five** jars. This is the
step that blocks people, because four of them are not on PyPI and the fifth is
not in SASHome.

| Jar | Comes from |
|---|---|
| `sas.core.jar` | SAS client installation |
| `sas.security.sspi.jar` | SAS client installation |
| `sas.svc.connection.jar` | SAS client installation |
| `log4j.jar` (or `log4j-api` + `log4j-core` on newer SAS) | SAS client installation |
| `saspyiom.jar` | **saspy itself** — `<site-packages>/saspy/java/` |

**In a real SASHome the four SAS jars are versioned**, e.g.
`sas.core_904400.0.0.20180221190000_f0f04fe.jar`, usually under
`SASVersionedJarRepository/eclipse/plugins/`. Searching for the bare name finds
nothing, which is why the setup script globs the stem:

```bash
find /opt/sas /usr/local/SASHome -name 'sas.core*.jar' 2>/dev/null
python -c "import saspy, pathlib; print(pathlib.Path(saspy.__file__).parent / 'java')"
```

The wizard searches the usual install roots plus saspy's own package
directory, prints what it found, and names the ones still missing with where
to get each. The classpath it builds is **explicit jar paths** joined by the
platform separator (`:` on Linux/macOS, `;` on Windows) rather than a `dir/*`
wildcard — the jars are typically spread across several directories, and a
wildcard would also drag in every other jar in `SASVersionedJarRepository`.

If the SAS jars are absent, the connection cannot be made from that machine no
matter what else is configured. Worth establishing before anyone is prompted
for a password.

## Diagnosing one — `scripts/sas_probe.py`

[`scripts/sas_probe.py`](../scripts/sas_probe.py) walks the connection path in
stages and returns a machine-readable code for every outcome.

```bash
python scripts/sas_probe.py --dry-run                       # list stages + codes, connect to nothing
python scripts/sas_probe.py --host sas.corp --port 8591 --user me   # SAS 9.4 via IOM
python scripts/sas_probe.py --viya https://viya.corp --token "$TOKEN"
python scripts/sas_probe.py --json > sas_probe.json
```

**Read-only by default.** The only code submitted is `%PUT` and a `PROC SQL`
`SELECT` with `outobs=1`. Nothing is created, dropped or updated unless
`--allow-write` is passed.

## Stages

`dependency → tcp → tls → auth → session → submit → library → table → dialect`

Network stages run even when the SAS client is missing, because "the host is
unreachable **and** saspy is not installed" is two tickets, not one. Everything
after the network is skipped when a prerequisite fails, since a submit failure
downstream of a dead connection tells you nothing.

The last stage is the one that decides feasibility: it submits the `PROC SQL`
constructs the generator actually emits (`CALCULATED`, `HAVING`, conditional
aggregation) and reports `SQL_DIALECT` if the server rejects them. A reachable,
authenticated server that cannot run the generated dialect is still a blocker.

## The 31 classified failure modes

Each carries a `retryable` flag — the operational question is whether waiting
and trying again has any chance.

| Code | Stage | Retryable | Meaning |
|---|---|---|---|
| `DEP_MISSING` | dependency | no | saspy / httpx not installed |
| `DEP_JAVA_MISSING` | dependency | no | IOM access needs a JRE on PATH |
| `CFG_INCOMPLETE` | config | no | host/port/auth not supplied |
| `CFG_NO_SASCFG` | config | no | saspy has no `sascfg_personal.py` |
| `NET_DNS` | tcp | no | hostname does not resolve |
| `NET_REFUSED` | tcp | **yes** | nothing listening on that port |
| `NET_TIMEOUT` | tcp | **yes** | firewall drop or server busy |
| `NET_UNREACHABLE` | tcp | **yes** | no route to host |
| `TLS_HANDSHAKE` | tls | no | TLS negotiation failed |
| `TLS_CERT_UNTRUSTED` | tls | no | corporate CA not in the trust store |
| `TLS_HOSTNAME_MISMATCH` | tls | no | certificate does not match the host |
| `TLS_EXPIRED` | tls | no | certificate expired |
| `AUTH_INVALID` | auth | no | credentials rejected |
| `AUTH_EXPIRED` | auth | **yes** | token expired — refresh and retry |
| `AUTH_LOCKED` | auth | no | account locked or disabled |
| `AUTH_MFA_REQUIRED` | auth | no | interactive second factor needed |
| `ENDPOINT_NOT_VIYA` | auth | no | reachable, but not a Viya API |
| `SESS_NO_LICENSE` | session | no | no licence seat available |
| `SESS_QUOTA` | session | **yes** | concurrent-session limit reached |
| `SESS_LAUNCH_FAILED` | session | **yes** | workspace server would not start |
| `SESS_TIMEOUT` | session | **yes** | session start timed out |
| `SUBMIT_SYNTAX` | submit | no | SAS rejected the code |
| `SUBMIT_AUTHZ` | submit | no | not authorised to run this |
| `SUBMIT_TIMEOUT` | submit | **yes** | statement exceeded the budget |
| `SUBMIT_DISCONNECTED` | submit | **yes** | session dropped mid-statement |
| `LIB_NOT_ASSIGNED` | library | no | libref does not exist / not assigned |
| `LIB_NO_ACCESS` | library | no | no read permission on the library |
| `TABLE_NOT_FOUND` | table | no | table does not exist in that library |
| `TABLE_NO_ACCESS` | table | no | no read permission on the table |
| `TABLE_LOCKED` | table | **yes** | locked by another process |
| `SQL_DIALECT` | dialect | no | `PROC SQL` rejected a generated construct |

## Two things that catch people out

**SAS reports failures in the log, not the return code.** A submit can come
back successful with `ERROR:` in the log. `classify_sas_log` treats the log as
the authority, which is why the retry policy must parse it rather than trust a
status.

**A 404 means different things at different stages.** During authentication it
means the base URL is not a Viya API; against a table it means the table is
missing. Classification is stage-aware — this was found by pointing the probe
at a non-Viya HTTPS host and getting `TABLE_NOT_FOUND`.

## Verified

The setup script is tested for the things that would bite quietly: the profile
has no password field, both files are written `0600`, the generated
`sascfg_personal.py` executes to the module saspy expects, a corrupt profile
file does not crash, and the wizard takes defaults instead of blocking when
there is no terminal — `getpass` under a pipe turned `--verify` into a hang
until that was fixed.

Network and TLS classification is tested against real hosts: DNS failure,
connection refused, and the three `badssl.com` certificate failures
(`wrong.host`, `expired`, `untrusted-root`) each produce their distinct code.
The SAS-log, HTTP and bookkeeping classifiers are unit-tested
([`tests/test_sas_probe.py`](../tests/test_sas_probe.py), 28 tests).

**Not verified:** no real SAS server was available, so the `session`, `submit`,
`library`, `table` and `dialect` stages have never executed against SAS. Their
log patterns come from SAS's documented messages, not from observation. Expect
to correct `classify_sas_log` on first contact with a real server.
