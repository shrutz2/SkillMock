"""Retrieval: query the session's FAISS index and map hits back to DB chunks."""
from config import Config
from models import resume_chunk as chunk_model
from services import embedding_service
from vector_store import faiss_index


def ensure_index(session_id):
    """Rebuild the in-memory FAISS index from DB chunks if it was lost.

    FAISS indices live in-process, so a server restart drops them. Since the
    chunk text is persisted in the DB, we can always reconstruct the index.
    """
    if faiss_index.has_index(session_id):
        return True
    rows = chunk_model.list_for_session(session_id)
    if not rows:
        return False
    texts = [r["chunk_text"] for r in rows]
    embeddings = embedding_service.embed_chunks(texts)
    faiss_index.build_index(session_id, embeddings)
    return True


def retrieve(session_id, query_text, k=None):
    """Return the top-k resume_chunk rows most relevant to ``query_text``."""
    k = k or Config.RETRIEVAL_TOP_K
    query_embedding = embedding_service.embed_query(query_text)
    vector_ids = faiss_index.search(session_id, query_embedding, k=k)

    chunks = []
    for vid in vector_ids:
        row = chunk_model.get_by_vector_id(session_id, vid)
        if row:
            chunks.append(row)
    return chunks
