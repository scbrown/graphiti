"""
Copyright 2024, Zep Software, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from collections.abc import Iterable
from typing import Literal

from .client import EmbedderClient, EmbedderConfig

SUPPORTED_MODELS = {
    'all-MiniLM-L6-v2': 384,
    'all-mpnet-base-v2': 768,
    'BAAI/bge-small-en-v1.5': 384,
}

LocalEmbeddingModel = Literal[
    'all-MiniLM-L6-v2',
    'all-mpnet-base-v2',
    'BAAI/bge-small-en-v1.5',
]

DEFAULT_LOCAL_MODEL: LocalEmbeddingModel = 'all-MiniLM-L6-v2'


class LocalEmbedderConfig(EmbedderConfig):
    embedding_model: LocalEmbeddingModel = DEFAULT_LOCAL_MODEL


class LocalEmbedder(EmbedderClient):
    """Local embedder using sentence-transformers models.

    Requires the `sentence-transformers` optional dependency:
        pip install graphiti-core[sentence-transformers]

    Supported models and their embedding dimensions:
        - all-MiniLM-L6-v2 (384)
        - all-mpnet-base-v2 (768)
        - BAAI/bge-small-en-v1.5 (384)
    """

    def __init__(self, config: LocalEmbedderConfig | None = None):
        if config is None:
            config = LocalEmbedderConfig(
                embedding_dim=SUPPORTED_MODELS[DEFAULT_LOCAL_MODEL],
            )
        self.config = config

        model_dim = SUPPORTED_MODELS.get(config.embedding_model)
        if model_dim is None:
            raise ValueError(
                f'Unsupported model: {config.embedding_model}. '
                f'Supported models: {list(SUPPORTED_MODELS.keys())}'
            )

        if config.embedding_dim != model_dim:
            raise ValueError(
                f'embedding_dim={config.embedding_dim} does not match '
                f'model {config.embedding_model} which produces {model_dim}-dim embeddings. '
                f'Set embedding_dim={model_dim} or omit it.'
            )

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                'sentence-transformers is required for LocalEmbedder. '
                'Install it with: pip install graphiti-core[sentence-transformers]'
            ) from None

        self.model = SentenceTransformer(config.embedding_model)

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        text = input_data if isinstance(input_data, str) else str(input_data)
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(input_data_list, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]
