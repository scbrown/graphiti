"""
Local sentence-transformers embedder for Graphiti.

Runs embeddings locally using sentence-transformers models, eliminating the need
for external API calls. Designed for the crew ontology system where crew agents
handle extraction and the embedder only needs to generate search vectors.

Supported models:
- all-MiniLM-L6-v2: 384 dims, ~80 MB, fast, good quality (default)
- all-mpnet-base-v2: 768 dims, ~420 MB, best quality for size
- BAAI/bge-small-en-v1.5: 384 dims, ~130 MB, strong benchmark scores

Usage:
    embedder = LocalEmbedder()  # defaults to all-MiniLM-L6-v2
    embedder = LocalEmbedder(model_name='all-mpnet-base-v2')
    embedder = LocalEmbedder(config=LocalEmbedderConfig(
        model_name='BAAI/bge-small-en-v1.5',
        embedding_dim=384,
    ))
"""

import asyncio
import logging
from collections.abc import Iterable
from functools import partial

from pydantic import Field

from .client import EmbedderClient, EmbedderConfig

logger = logging.getLogger(__name__)

# Model name -> embedding dimension mapping
MODEL_DIMENSIONS: dict[str, int] = {
    'all-MiniLM-L6-v2': 384,
    'sentence-transformers/all-MiniLM-L6-v2': 384,
    'all-mpnet-base-v2': 768,
    'sentence-transformers/all-mpnet-base-v2': 768,
    'BAAI/bge-small-en-v1.5': 384,
}

DEFAULT_MODEL = 'all-MiniLM-L6-v2'


class LocalEmbedderConfig(EmbedderConfig):
    """Configuration for the local sentence-transformers embedder."""

    model_name: str = Field(default=DEFAULT_MODEL)
    embedding_dim: int = Field(default=384, frozen=True)
    device: str | None = Field(
        default=None,
        description='Device to run the model on (e.g. "cpu", "cuda"). None = auto-detect.',
    )


class LocalEmbedder(EmbedderClient):
    """Local embedder using sentence-transformers models.

    Generates embeddings locally without any API calls. The model is loaded
    lazily on first use and cached for subsequent calls.
    """

    def __init__(
        self,
        config: LocalEmbedderConfig | None = None,
        model_name: str | None = None,
    ):
        if config is None:
            if model_name is not None:
                dim = MODEL_DIMENSIONS.get(model_name, 384)
                config = LocalEmbedderConfig(model_name=model_name, embedding_dim=dim)
            else:
                config = LocalEmbedderConfig()

        self.config = config
        self._model = None

    @property
    def model(self):
        """Lazy-load the sentence-transformers model on first access."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    'sentence-transformers is required for LocalEmbedder. '
                    'Install it with: pip install sentence-transformers'
                )
            logger.info('Loading sentence-transformers model: %s', self.config.model_name)
            kwargs = {}
            if self.config.device is not None:
                kwargs['device'] = self.config.device
            self._model = SentenceTransformer(self.config.model_name, **kwargs)

            # Verify embedding dimension matches config
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim != self.config.embedding_dim:
                logger.warning(
                    'Model %s produces %d-dim embeddings but config specifies %d. '
                    'Using actual model dimension.',
                    self.config.model_name,
                    actual_dim,
                    self.config.embedding_dim,
                )
        return self._model

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        """Generate an embedding for a single input.

        Args:
            input_data: Text string, list of strings (first element used),
                        or token IDs to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        if isinstance(input_data, str):
            text = input_data
        elif isinstance(input_data, list) and len(input_data) > 0 and isinstance(input_data[0], str):
            text = input_data[0]
        else:
            # Token IDs or other iterable — convert to list and encode
            text = str(list(input_data))

        # Run the synchronous model.encode in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, partial(self.model.encode, text, normalize_embeddings=True)
        )
        return embedding.tolist()[: self.config.embedding_dim]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of inputs.

        Args:
            input_data_list: List of text strings to embed.

        Returns:
            List of embedding vectors (list of lists of floats).
        """
        if not input_data_list:
            return []

        # Run the synchronous model.encode in a thread pool
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, partial(self.model.encode, input_data_list, normalize_embeddings=True)
        )
        dim = self.config.embedding_dim
        return [e.tolist()[:dim] for e in embeddings]
