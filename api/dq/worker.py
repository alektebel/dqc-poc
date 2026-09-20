"""One rule in, one JSON-serialisable result out.

This is the unit of work the whole design turns on: everything a single
rule needs arrives as arguments, and everything it produces comes back as
a plain dict. Locally a thread calls it; in AWS a Lambda invocation would
wrap exactly this call and nothing else.

It does not persist anything. Deciding whether a result is worth keeping
belongs to whoever asked for it — a reviewer confirming a preview, or the
job runner storing a batch — and keeping that decision out of here is
what lets the same call serve both.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from api.dq.pipeline import RuleOutcome, run_rule_pipeline

__all__ = ["run_rule", "outcome_to_dict", "ExecutorFactory"]

# A factory rather than an executor: each worker needs its OWN handle on
# the data. The uploaded file's SQLite connection is documented as
# strictly sequential, and DB-API connections are not thread-safe either,
# so sharing one across parallel rules would be a race in both worlds.
ExecutorFactory = Callable[[], Any]


def run_rule(regla: str, *, fields: list, table_name: str, executor,
             client, comentario: str = "",
             prev_id: str = "",
             value_grounding: bool = False,
             semantic_judge: bool = False,
             on_progress: Callable[[dict], None] | None = None,
             ) -> tuple[RuleOutcome, list[dict]]:
    """Drive the agent loop for one rule to completion.

    ``on_progress`` receives each progress payload as it happens (the job
    runner writes it to the item's row so the screen can poll it). The
    events are also returned, for callers that want them afterwards.
    """
    entry = {"id": 1, "regla": regla, "accion": regla, "prev_id": prev_id}
    gen = run_rule_pipeline(
        entry, fields, table_name, executor, client=client,
        value_grounding=value_grounding, semantic_judge=semantic_judge,
        seed_feedback=[comentario] if comentario.strip() else None)
    events: list[dict] = []
    while True:
        try:
            event = next(gen)
        except StopIteration as stop:
            return stop.value, events
        events.append(event)
        if on_progress is not None:
            on_progress(event)


def outcome_to_dict(outcome: RuleOutcome,
                    explanation_text: Callable[[Any], str] | None = None
                    ) -> dict:
    """The outcome as plain JSON — a Lambda's response payload."""
    item = outcome.items[0] if outcome.items else None
    explicacion = outcome.explicacion
    if explanation_text is not None:
        explicacion = explanation_text(explicacion)
    return {
        "estado": outcome.estado,
        "error": outcome.error,
        "falta": outcome.falta,
        "campos": outcome.campos,
        "dqc": item.model_dump() if item else None,
        "validacion": outcome.validacion,
        "explicacion": explicacion,
        "atribucion": outcome.atribucion,
        "trace": outcome.trace,
        "agents": outcome.agents,
    }


def iter_rules(lines: Iterable[str]) -> list[str]:
    """Non-empty rule lines, in order, deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        rule = line.strip()
        if rule and rule not in seen:
            seen.add(rule)
            out.append(rule)
    return out
