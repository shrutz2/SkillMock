"""Answer model - candidate answers plus specificity score and feedback."""
from datetime import datetime

from db.database import execute


def create(question_id, answer_text, specificity_score, feedback_text):
    return execute(
        """INSERT INTO answers (question_id, answer_text, specificity_score, feedback_text, created_at)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            question_id,
            answer_text,
            specificity_score,
            feedback_text,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
        commit=True,
    )


def get_for_question(question_id):
    return execute(
        "SELECT * FROM answers WHERE question_id = %s ORDER BY id DESC",
        (question_id,),
        fetchone=True,
    )
