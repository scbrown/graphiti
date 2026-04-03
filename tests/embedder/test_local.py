"""Tests for the local sentence-transformers embedder."""

import numpy as np
import pytest

from graphiti_core.embedder.local import (
    DEFAULT_MODEL,
    MODEL_DIMENSIONS,
    LocalEmbedder,
    LocalEmbedderConfig,
)


@pytest.fixture
def embedder():
    """Create a LocalEmbedder with the default model."""
    return LocalEmbedder()


@pytest.fixture
def embedder_mpnet():
    """Create a LocalEmbedder with all-mpnet-base-v2."""
    return LocalEmbedder(model_name='all-mpnet-base-v2')


class TestLocalEmbedderConfig:
    def test_default_config(self):
        config = LocalEmbedderConfig()
        assert config.model_name == DEFAULT_MODEL
        assert config.embedding_dim == 384
        assert config.device is None

    def test_custom_model(self):
        config = LocalEmbedderConfig(model_name='all-mpnet-base-v2', embedding_dim=768)
        assert config.model_name == 'all-mpnet-base-v2'
        assert config.embedding_dim == 768

    def test_custom_device(self):
        config = LocalEmbedderConfig(device='cpu')
        assert config.device == 'cpu'


class TestLocalEmbedderInit:
    def test_default_init(self):
        embedder = LocalEmbedder()
        assert embedder.config.model_name == DEFAULT_MODEL
        assert embedder.config.embedding_dim == 384
        assert embedder._model is None  # Lazy loading

    def test_init_with_model_name(self):
        embedder = LocalEmbedder(model_name='all-mpnet-base-v2')
        assert embedder.config.model_name == 'all-mpnet-base-v2'
        assert embedder.config.embedding_dim == 768

    def test_init_with_config(self):
        config = LocalEmbedderConfig(model_name='BAAI/bge-small-en-v1.5', embedding_dim=384)
        embedder = LocalEmbedder(config=config)
        assert embedder.config.model_name == 'BAAI/bge-small-en-v1.5'

    def test_init_unknown_model_defaults_384(self):
        embedder = LocalEmbedder(model_name='some-custom-model')
        assert embedder.config.embedding_dim == 384


class TestModelDimensions:
    def test_known_models(self):
        assert MODEL_DIMENSIONS['all-MiniLM-L6-v2'] == 384
        assert MODEL_DIMENSIONS['all-mpnet-base-v2'] == 768
        assert MODEL_DIMENSIONS['BAAI/bge-small-en-v1.5'] == 384


@pytest.mark.asyncio
class TestLocalEmbedderCreate:
    async def test_create_string(self, embedder):
        result = await embedder.create('Hello world')
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)

    async def test_create_returns_normalized(self, embedder):
        result = await embedder.create('Hello world')
        # Normalized embeddings should have unit L2 norm (approximately)
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 0.01

    async def test_create_list_of_strings(self, embedder):
        result = await embedder.create(['Hello world', 'Goodbye'])
        assert isinstance(result, list)
        assert len(result) == 384

    async def test_create_different_texts_different_embeddings(self, embedder):
        result1 = await embedder.create('The cat sat on the mat')
        result2 = await embedder.create('Quantum physics and black holes')
        # Different texts should produce different embeddings
        assert result1 != result2

    async def test_create_similar_texts_close_embeddings(self, embedder):
        result1 = await embedder.create('The dog is sleeping')
        result2 = await embedder.create('The puppy is resting')
        # Similar texts should have high cosine similarity
        similarity = np.dot(result1, result2)
        assert similarity > 0.5  # Normalized vectors, dot product = cosine similarity

    async def test_create_empty_string(self, embedder):
        result = await embedder.create('')
        assert isinstance(result, list)
        assert len(result) == 384


@pytest.mark.asyncio
class TestLocalEmbedderCreateBatch:
    async def test_create_batch(self, embedder):
        texts = ['Hello world', 'Goodbye world', 'Test embedding']
        results = await embedder.create_batch(texts)
        assert len(results) == 3
        assert all(len(r) == 384 for r in results)
        assert all(isinstance(r, list) for r in results)

    async def test_create_batch_empty(self, embedder):
        results = await embedder.create_batch([])
        assert results == []

    async def test_create_batch_single(self, embedder):
        results = await embedder.create_batch(['Single text'])
        assert len(results) == 1
        assert len(results[0]) == 384

    async def test_create_batch_consistency(self, embedder):
        """Batch results should match individual create results."""
        texts = ['Hello', 'World']
        batch_results = await embedder.create_batch(texts)
        individual_results = [await embedder.create(t) for t in texts]

        for batch_r, indiv_r in zip(batch_results, individual_results):
            # Should be very close (floating point may differ slightly)
            np.testing.assert_allclose(batch_r, indiv_r, atol=1e-5)
