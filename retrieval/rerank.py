from functools import cache

import torch
from sentence_transformers import CrossEncoder

from core import config

# Measured on the eval set (M2, 20 candidates): 512 tokens took ~11 s per question in float32;
# 256 tokens in float16 took ~4.7 s with Hit@5 no worse. Half precision only on a GPU, since
# float16 is slow on CPU.
MAX_TOKENS = 256


@cache
def model() -> CrossEncoder:
    gpu = torch.backends.mps.is_available() or torch.cuda.is_available()
    kwargs = {"dtype": torch.float16} if gpu else {}
    return CrossEncoder(config.RERANK_MODEL, max_length=MAX_TOKENS, model_kwargs=kwargs)


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    """Relevance of each passage to the query, 0-1 (sigmoid of the model's logit)."""
    if not passages:
        return []
    return model().predict([(query, p) for p in passages]).tolist()
