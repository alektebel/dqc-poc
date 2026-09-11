# Submitting generated DQCs to a SAS server — feasibility

Nothing in this repo has ever connected to a SAS server. The generator emits
SAS/`PROC SQL`, `dqc_react.static_validate` checks it without executing, and
dynamic validation runs against a local SQLite fixture. Before designing
anything that submits generated code to a real server, the failure surface has
to be known.

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

Network and TLS classification is tested against real hosts: DNS failure,
connection refused, and the three `badssl.com` certificate failures
(`wrong.host`, `expired`, `untrusted-root`) each produce their distinct code.
The SAS-log, HTTP and bookkeeping classifiers are unit-tested
([`tests/test_sas_probe.py`](../tests/test_sas_probe.py), 28 tests).

**Not verified:** no real SAS server was available, so the `session`, `submit`,
`library`, `table` and `dialect` stages have never executed against SAS. Their
log patterns come from SAS's documented messages, not from observation. Expect
to correct `classify_sas_log` on first contact with a real server.
