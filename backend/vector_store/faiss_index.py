"""Step 4: FAISS index (in-process vector store).

Indices are held in memory keyed by session_id. This matches the architecture's
single-resume-at-a-time scope; the chunk text itself is persisted in MySQL so a
session can always be reconstructed.
"""
import faiss
import numpy as np

# session_id -> faiss index
_indices = {}


def build_index(session_id, embeddings):
    """Build and store an L2 flat index for a session."""
    embeddings = np.asarray(embeddings, dtype="float32")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    _indices[session_id] = index
    return index


def has_index(session_id):
    return session_id in _indices


def search(session_id, query_embedding, k=3):
    """Return the FAISS vector ids (== chunk indices) of the top-k matches."""
    index = _indices.get(session_id)
    if index is None:
        return []
    query = np.asarray([query_embedding], dtype="float32")
    k = min(k, index.ntotal)
    distances, indices = index.search(query, k)
    return [int(i) for i in indices[0] if i != -1]
