"""Resume chunk model - semantic pieces of the resume with their FAISS ids."""
from db.database import execute


def create(session_id, chunk_text, chunk_index, faiss_vector_id):
    return execute(
        """INSERT INTO resume_chunks (session_id, chunk_text, chunk_index, faiss_vector_id)
           VALUES (%s, %s, %s, %s)""",
        (session_id, chunk_text, chunk_index, faiss_vector_id),
        commit=True,
    )


def get(chunk_id):
    return execute(
        "SELECT * FROM resume_chunks WHERE id = %s", (chunk_id,), fetchone=True
    )


def list_for_session(session_id):
    return execute(
        "SELECT * FROM resume_chunks WHERE session_id = %s ORDER BY chunk_index",
        (session_id,),
        fetchall=True,
    )


def get_by_vector_id(session_id, faiss_vector_id):
    return execute(
        "SELECT * FROM resume_chunks WHERE session_id = %s AND faiss_vector_id = %s",
        (session_id, faiss_vector_id),
        fetchone=True,
    )
