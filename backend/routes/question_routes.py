"""POST /api/questions/generate - RAG-retrieve chunks, generate questions."""
import threading

from flask import Blueprint, jsonify, request

from config import Config
from models import question as question_model
from models import resume_chunk as chunk_model
from models import session as session_model
from routes.auth import require_session, session_id_from_body
from services.rate_limit import rate_limit
from services import question_service, retrieval_service

question_bp = Blueprint("questions", __name__)

# Serialize generation so concurrent requests for the same session (e.g. React
# StrictMode double-invoking the effect) can't each create a full batch.
_gen_lock = threading.Lock()

# Seed themes drive retrieval so questions come from the most substantive
# resume sections instead of one-line skill lists.
_SEED_QUERIES = [
    "technical project the candidate built and the decisions they made",
    "system design, architecture, scaling, or performance tradeoffs",
    "specific technologies, frameworks, and measurable results or metrics",
    "hardest technical problem the candidate solved",
    "work experience and engineering responsibilities",
]


@question_bp.route("/api/questions/generate", methods=["POST"])
@rate_limit(limit=10, window_seconds=300, scope="questions")
@require_session(session_id_from_body)
def generate_questions():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    role_level = data.get("role_level")  # #1 role calibration
    if role_level not in (None, "Fresher", "Junior", "SDE-1"):
        return jsonify({"error": "Invalid role_level"}), 400

    with _gen_lock:
        # Return already-generated questions if this session has them (re-checked
        # inside the lock so a second concurrent request never double-generates).
        existing = question_model.list_for_session(session_id)
        if existing:
            return jsonify({"session_id": session_id, "questions": _serialize(existing)})

        if not retrieval_service.ensure_index(session_id):
            return jsonify({"error": "No resume content for this session"}), 404

        n = Config.QUESTIONS_PER_SESSION
        selected_chunks = _select_chunks(session_id, n)

        questions = []
        asked = []
        for chunk in selected_chunks:
            text = question_service.generate_question(
                chunk["chunk_text"], role_level=role_level, avoid=asked
            )
            qid = question_model.create(session_id, text, chunk["id"])
            questions.append(
                {"id": qid, "question_text": text, "source_chunk_id": chunk["id"]}
            )
            asked.append(text)

    return jsonify({"session_id": session_id, "questions": questions}), 201


def _select_chunks(session_id, n):
    """Return exactly ``n`` chunk assignments.

    Gathers the distinct substantive chunks (retrieval hits first, then the rest
    by length), then cycles through them to reach ``n`` - so resumes with fewer
    than ``n`` sections still yield ``n`` questions (the generator is told to
    vary the angle when a section repeats).
    """
    ordered = []
    seen = set()

    for seed in _SEED_QUERIES:
        for chunk in retrieval_service.retrieve(session_id, seed, k=1):
            if chunk["id"] not in seen:
                seen.add(chunk["id"])
                ordered.append(chunk)

    for chunk in sorted(
        chunk_model.list_for_session(session_id),
        key=lambda c: len(c["chunk_text"]),
        reverse=True,
    ):
        if chunk["id"] not in seen:
            seen.add(chunk["id"])
            ordered.append(chunk)

    if not ordered:
        return []

    return [ordered[i % len(ordered)] for i in range(n)]


def _serialize(rows):
    return [
        {
            "id": r["id"],
            "question_text": r["question_text"],
            "source_chunk_id": r["source_chunk_id"],
        }
        for r in rows
    ]
