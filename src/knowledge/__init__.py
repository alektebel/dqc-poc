"""LLM client + BCBS 239 classification + SQL attribution.

What the DQC generator needs and nothing else: the regulation knowledge
graph, its embeddings and the change-log GraphRAG were research channels
this PoC does not use, so they no longer ship.
"""

from .llm_client import (
    ChatResponse,
    GemmaClient,        # legacy alias
    LocalLLMClient,
    get_client,
    get_inspect_client,
    reset_client,
)

__all__ = [
    "ChatResponse",
    "GemmaClient",
    "LocalLLMClient",
    "get_client",
    "get_inspect_client",
    "reset_client",
]
