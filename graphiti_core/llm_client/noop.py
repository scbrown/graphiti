"""NoOp LLM client — safety stub for configurations that bypass LLM extraction.

When Graphiti is used with crew-driven extraction (add_fact_triple / ingest_extracted_episode),
no LLM calls should occur. This client satisfies the LLMClient ABC requirement while raising
immediately if the LLM pipeline is accidentally invoked.

See: docs/design/crew-ontology-triple-store.md
Bead: aegis-96n
"""

import typing

from pydantic import BaseModel

from .client import LLMClient
from .config import DEFAULT_MAX_TOKENS, LLMConfig, ModelSize


class NoOpLLMClient(LLMClient):
    """LLM client that raises on any generation attempt.

    Pass this to Graphiti's constructor when LLM extraction is not used.
    If code accidentally calls the LLM pipeline, this will fail loudly
    rather than silently producing garbage.
    """

    def __init__(self):
        super().__init__(config=LLMConfig(), cache=False)

    async def _generate_response(
        self,
        messages: list,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        raise RuntimeError(
            'LLM pipeline disabled — use /episodes/complete for crew-driven extraction'
        )
