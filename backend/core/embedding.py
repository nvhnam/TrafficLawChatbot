import logging
from sentence_transformers import SentenceTransformer
from backend.config import MODEL_EMBEDDING
from backend.core.container import ServiceContainer

logger = logging.getLogger(__name__)


def _load_embedding_model() -> SentenceTransformer:
    try:
        logger.info("Loading embedding model '%s' from local cache (no network)...", MODEL_EMBEDDING)
        return SentenceTransformer(MODEL_EMBEDDING, device="cpu", local_files_only=True)
    except Exception as exc:
        logger.warning(
            "Local-only load of '%s' failed (%s); falling back to an online download.",
            MODEL_EMBEDDING, exc,
        )
        return SentenceTransformer(MODEL_EMBEDDING, device="cpu")


def get_embedding_model() -> SentenceTransformer:
    return ServiceContainer.get("embedding_model", _load_embedding_model)
