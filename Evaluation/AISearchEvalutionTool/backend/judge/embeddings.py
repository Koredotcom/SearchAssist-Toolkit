"""Sentence-Transformers based semantic similarity.

Lazy-loaded singleton — the model loads on first use (downloads ~80 MB on
first ever run, then cached in ~/.cache/huggingface/).
"""
from __future__ import annotations

import logging
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_MAX_LOAD_ATTEMPTS = 3
_RETRY_DELAY = 2  # seconds between load attempts

_model = None          # SentenceTransformer instance, or False if permanently broken
_load_attempts = 0
_model_lock = threading.Lock()


def _get_model():
    """Return the singleton model, loading it on first call.

    Retries up to _MAX_LOAD_ATTEMPTS times. After exhausting all attempts,
    sets _model to False so callers know it's permanently unavailable and
    stop retrying on every subsequent call.
    """
    global _model, _load_attempts
    if _model is not None:
        return _model  # False means broken; truthy means ready
    with _model_lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer
        while _load_attempts < _MAX_LOAD_ATTEMPTS:
            _load_attempts += 1
            try:
                logger.info(
                    "Loading sentence-transformers model: %s (attempt %d/%d)",
                    _MODEL_NAME, _load_attempts, _MAX_LOAD_ATTEMPTS,
                )
                _model = SentenceTransformer(_MODEL_NAME)
                logger.info("Sentence-transformers model ready")
                return _model
            except Exception as exc:
                logger.warning(
                    "Model load attempt %d/%d failed: %s",
                    _load_attempts, _MAX_LOAD_ATTEMPTS, exc,
                )
                if _load_attempts < _MAX_LOAD_ATTEMPTS:
                    time.sleep(_RETRY_DELAY)
        # All attempts exhausted — mark as permanently broken
        logger.error(
            "sentence-transformers model unavailable after %d attempts — "
            "Case 1 verdicts will be recorded as 'no verdict'.",
            _MAX_LOAD_ATTEMPTS,
        )
        _model = False
    return _model


def semantic_similarity(text_a: Optional[str], text_b: Optional[str]) -> Optional[float]:
    """Cosine similarity in [0, 1] between two strings.

    Returns None if either side is empty / None. Errors fall back to None
    rather than crashing the eval pipeline.
    """
    a = (text_a or "").strip()
    b = (text_b or "").strip()
    if not a or not b:
        return None
    try:
        model = _get_model()
        if not model:  # False sentinel — permanently broken
            return None
        emb = model.encode([a, b], normalize_embeddings=True, convert_to_numpy=True)
        # Cosine similarity on normalized vectors == dot product
        sim = float((emb[0] * emb[1]).sum())
        # Clamp to [0, 1] — embeddings already normalized; sim should be in [-1, 1]
        # but for relevant texts it's typically [0, 1]. Negative → treat as 0.
        return round(max(0.0, min(1.0, sim)), 4)
    except Exception as exc:
        logger.warning("semantic_similarity failed: %s", exc)
        return None


def warm_up() -> bool:
    """Pre-load the model; returns True if successful, False otherwise.

    Call this once during app startup to absorb the first-load latency before
    serving requests. After _MAX_LOAD_ATTEMPTS failures the model is marked
    broken and this returns False — no further load attempts will be made.
    """
    model = _get_model()
    return bool(model)
