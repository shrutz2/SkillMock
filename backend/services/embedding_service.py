"""Step 3: Embedding (free, local, no API cost via sentence-transformers)."""
import numpy as np

from config import Config

_model = None


def _get_model():
    """Lazy-load the model so importing this module stays cheap."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(Config.EMBEDDING_MODEL)
    return _model


def embed_chunks(chunks):
    """Embed a list of texts -> float32 ndarray (n, dim)."""
    model = _get_model()
    embeddings = model.encode(chunks, convert_to_numpy=True)
    return np.asarray(embeddings, dtype="float32")


def embed_query(text):
    """Embed a single query string -> float32 ndarray (dim,)."""
    return embed_chunks([text])[0]
