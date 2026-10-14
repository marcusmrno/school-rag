from functools import cache

from sentence_transformers import SentenceTransformer

from core import config


@cache
def model() -> SentenceTransformer:
    return SentenceTransformer(config.EMBED_MODEL)


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = model().encode(
        texts, batch_size=16, normalize_embeddings=True, show_progress_bar=len(texts) > 50
    )
    return vectors.tolist()
