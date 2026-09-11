"""Teacher-forced log-probability scoring — the signal ContextCite needs.

:func:`attribute_by_surrogate` asks how likely a *fixed* response is under an
ablated context. That requires scoring tokens the model did not just generate,
which most chat APIs will not do.

What each backend can do:

======================  =========================================================
Bedrock (Nova)          **No.** ``ConverseResponse`` carries output, stopReason,
                        usage, metrics and trace; ``InferenceConfiguration`` only
                        maxTokens, temperature, topP and stopSequences. No
                        logprobs at all, so surrogate attribution is impossible
                        against Nova. Use ``attribute_by_ablation`` there.
OpenAI-compatible       **Yes**, via ``/v1/completions`` with ``echo=true``,
(REGLLM_API_URL)        which returns ``prompt_logprobs`` — per-token
                        log-probabilities of the prompt itself. Putting the
                        context *and* the response in the prompt teacher-forces
                        the response and scores it. Verified against
                        ``api.nan.builders`` (qwen3.6).
Local GGUF              **Yes**, llama-cpp-python exposes ``logprobs`` on
(GGUF_MODEL_PATH)       evaluation, with no per-call cost and no rate limit —
                        the best option for a large attribution study.
======================  =========================================================

So interpretability does not require changing the production backend: generate
with Nova, attribute with a scorer that can return logprobs. The caveat is that
the attribution then describes *that* model's dependence on the context. To
make claims about the deployed model, generate and score with the same one.
"""

from __future__ import annotations

import os
from typing import Callable, Iterable, Sequence

__all__ = ["openai_logprob_scorer", "build_prompt", "LogprobUnavailable"]


class LogprobUnavailable(RuntimeError):
    """The configured backend cannot score a fixed continuation."""


def build_prompt(units: Iterable, response: str, *, instruction: str = "") -> str:
    """Context + instruction + response as one string, for echo scoring.

    The response goes last so that the tokens being scored are conditioned on
    exactly the context units supplied.
    """
    blocks = []
    if instruction:
        blocks.append(instruction.strip())
    ctx = "\n".join(
        f"- {getattr(u, 'label', '') or getattr(u, 'key', '')}: {getattr(u, 'text', '')}".rstrip(": ")
        for u in units)
    if ctx:
        blocks.append("CONTEXTO:\n" + ctx)
    blocks.append("RESPUESTA:\n" + response)
    return "\n\n".join(blocks)


def openai_logprob_scorer(
    response: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    instruction: str = "",
    timeout: float = 120.0,
) -> Callable[[Sequence], float]:
    """A ``logprob(units) -> float`` callable for :func:`attribute_by_surrogate`.

    Scores only the tokens of ``response``: the prompt is rebuilt per subset,
    so the response's token offset moves, and the returned sum is taken over
    the trailing ``len(response_tokens)`` entries of ``prompt_logprobs``.
    """
    import httpx

    base_url = (base_url or os.getenv("REGLLM_API_URL") or "").rstrip("/")
    api_key = api_key or os.getenv("REGLLM_API_KEY") or ""
    model = model or os.getenv("REGLLM_API_MODEL") or ""
    if not base_url or not model:
        raise LogprobUnavailable(
            "Set REGLLM_API_URL and REGLLM_API_MODEL (and REGLLM_API_KEY) to an "
            "OpenAI-compatible endpoint that supports /v1/completions echo.")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Where the response starts is found by scoring the prompt without it and
    # taking the length difference, which avoids needing the tokenizer.
    def _prompt_logprobs(prompt: str) -> list:
        payload = {"model": model, "prompt": prompt, "max_tokens": 0,
                   "echo": True, "logprobs": 1}
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{base_url}/v1/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise LogprobUnavailable(f"No choices returned by {base_url}")
        lps = choices[0].get("prompt_logprobs")
        if lps is None:
            raise LogprobUnavailable(
                f"{base_url} returned no prompt_logprobs — this endpoint cannot "
                "teacher-force. Use attribute_by_ablation instead.")
        return lps

    def score(units: Sequence) -> float:
        with_response = build_prompt(units, response, instruction=instruction)
        without = build_prompt(units, "", instruction=instruction)
        full = _prompt_logprobs(with_response)
        prefix = _prompt_logprobs(without)
        tail = full[len(prefix):] if len(full) > len(prefix) else full
        total = 0.0
        for entry in tail:
            if not entry:
                continue
            # {token_id: {"logprob": x, ...}} — take the realised token, which
            # is the one with rank 1 among those reported for that position.
            best = None
            for info in entry.values():
                if not isinstance(info, dict):
                    continue
                if info.get("rank") == 1 or best is None:
                    best = info
                    if info.get("rank") == 1:
                        break
            if best is not None:
                total += float(best.get("logprob", 0.0))
        return total

    return score
