"""Question model - LLM-generated, resume-specific interview questions."""
from datetime import datetime

from db.database import execute


def create(session_id, question_text, source_chunk_id):
    return execute(
        """INSERT INTO questions (session_id, question_text, source_chunk_id, created_at)
           VALUES (%s, %s, %s, %s)""",
        (
            session_id,
            question_text,
            source_chunk_id,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
        commit=True,
    )


def get(question_id):
    return execute(
        "SELECT * FROM questions WHERE id = %s", (question_id,), fetchone=True
    )


def list_for_session(session_id):
    return execute(
        "SELECT * FROM questions WHERE session_id = %s ORDER BY id",
        (session_id,),
        fetchall=True,
    )
