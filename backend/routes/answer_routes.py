"""POST /api/answers/evaluate and GET /api/sessions/<id>/summary."""
from flask import Blueprint, jsonify, request

from models import answer as answer_model
from models import question as question_model
from models import resume_chunk as chunk_model
from models import session as session_model
from routes.auth import provided_token, require_session, session_id_from_url
from services import evaluation_service
from services.rate_limit import rate_limit

answer_bp = Blueprint("answers", __name__)


@answer_bp.route("/api/answers/evaluate", methods=["POST"])
@rate_limit(limit=40, window_seconds=300, scope="evaluate")
def evaluate_answer():
    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    answer_text = (data.get("answer_text") or "")[:8000].strip()

    if not question_id:
        return jsonify({"error": "question_id is required"}), 400
    if not answer_text:
        return jsonify({"error": "answer_text is required"}), 400

    question = question_model.get(question_id)
    if not question:
        return jsonify({"error": "Unknown question_id"}), 404

    # A question belongs to a session, so answering it requires that session's
    # token - otherwise question ids could be walked the same way session ids
    # could.
    if not session_model.token_matches(question["session_id"], provided_token()):
        return jsonify({"error": "Not authorized for this session"}), 403

    source_chunk = chunk_model.get(question["source_chunk_id"])
    chunk_text = source_chunk["chunk_text"] if source_chunk else ""

    score, feedback, improvement = evaluation_service.evaluate_answer(
        question["question_text"], answer_text, chunk_text
    )

    answer_id = answer_model.create(question_id, answer_text, score, feedback)

    return jsonify(
        {
            "answer_id": answer_id,
            "question_id": question_id,
            "specificity_score": score,
            "feedback_text": feedback,
            "improvement_text": improvement,
        }
    ), 201


@answer_bp.route("/api/sessions/<int:session_id>", methods=["DELETE"])
@require_session(session_id_from_url)
def delete_session(session_id):
    """Erase everything stored for a session - the resume text, questions and
    answers. Requires the session token, so only the owner can trigger it."""
    removed = session_model.purge(session_id)
    return jsonify({"deleted": True, "session_id": session_id, "rows_removed": removed})


@answer_bp.route("/api/sessions/<int:session_id>/summary", methods=["GET"])
@require_session(session_id_from_url)
def session_summary(session_id):
    session = session_model.get(session_id)
    questions = question_model.list_for_session(session_id)
    items = []
    scores = []
    for q in questions:
        ans = answer_model.get_for_question(q["id"])
        if ans and ans["specificity_score"] is not None:
            scores.append(ans["specificity_score"])
        items.append(
            {
                "question_id": q["id"],
                "question_text": q["question_text"],
                "answer_text": ans["answer_text"] if ans else None,
                "specificity_score": ans["specificity_score"] if ans else None,
                "feedback_text": ans["feedback_text"] if ans else None,
            }
        )

    avg = round(sum(scores) / len(scores), 2) if scores else None
    return jsonify(
        {
            "session_id": session_id,
            "resume_filename": session["resume_filename"],
            "answered": len(scores),
            "total_questions": len(questions),
            "average_score": avg,
            "items": items,
        }
    )
