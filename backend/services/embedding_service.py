"""Step 3: Embedding.

Two backends, both running the same all-MiniLM-L6-v2 model locally so resume
text never leaves the machine for this step:

  onnx  - fastembed on onnxruntime. ~50 MB of dependencies, which is what makes
          the app deployable on a small free-tier instance.
  torch - sentence-transformers. ~1.5 GB, mostly torch and its CUDA build.

The vectors are identical between the two (cosine similarity 1.0), so this is a
packaging choice, not a quality one. ONNX is the default; torch stays available
via EMBEDDING_BACKEND=torch.
"""
import numpy as np

from config import Config

_model = None
_backend = None

MODEL_ALIASES = {
    # fastembed wants the fully qualified hub id.
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
}


def _load():
    """Load the configured backend once, falling back to torch if onnx is absent."""
    global _model, _backend
    if _model is not None:
        return _model, _backend

    want = (Config.EMBEDDING_BACKEND or "onnx").lower()

    if want == "onnx":
        try:
            from fastembed import TextEmbedding

            name = MODEL_ALIASES.get(Config.EMBEDDING_MODEL, Config.EMBEDDING_MODEL)
            _model, _backend = TextEmbedding(name), "onnx"
            return _model, _backend
        except Exception as exc:
            print(f"[embeddings] onnx backend unavailable ({exc}); trying torch.")

    from sentence_transformers import SentenceTransformer

    _model, _backend = SentenceTransformer(Config.EMBEDDING_MODEL), "torch"
    return _model, _backend


def embed_chunks(chunks):
    """Embed a list of texts -> float32 ndarray (n, dim)."""
    if not chunks:
        return np.zeros((0, 384), dtype="float32")

    model, backend = _load()
    if backend == "onnx":
        vectors = list(model.embed(chunks))
    else:
        vectors = model.encode(chunks, convert_to_numpy=True)
    return np.asarray(vectors, dtype="float32")


def embed_query(text):
    """Embed a single query string -> float32 ndarray (dim,)."""
    return embed_chunks([text])[0]


def backend_name():
    """Which backend is actually loaded, for the health endpoint."""
    return _backend or (Config.EMBEDDING_BACKEND or "onnx")
