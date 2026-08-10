"""POST /api/resume/report - pre-interview resume feedback (#4, #5) + optional JD fit (#2)."""
import hashlib

from flask import Blueprint, jsonify, request

from models import resume_chunk as chunk_model
from models import session as session_model
from routes.auth import require_session, session_id_from_body
from services.rate_limit import rate_limit
from services import analysis_service, ats_service, retrieval_service

report_bp = Blueprint("report", __name__)


@report_bp.route("/api/resume/report", methods=["POST"])
@rate_limit(limit=20, window_seconds=300, scope="report")
@require_session(session_id_from_body)
def resume_report():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    jd_text = (data.get("job_description") or "")[:20000].strip()

    chunks = chunk_model.list_for_session(session_id)
    if not chunks:
        return jsonify({"error": "No resume content for this session"}), 404

    resume_text = "\n".join(c["chunk_text"] for c in chunks)

    parse_meta = session_model.get_parse_meta(session_id)
    ats = ats_service.ats_report(resume_text, jd_text, parse_meta=parse_meta)

    # Resume analysis is cached per session AND keyed by a hash of the resume
    # text: the same resume always returns the same result (so pasting a JD
    # doesn't silently regenerate it), while any new resume - new session or
    # re-upload - produces a different hash and is always recomputed fresh.
    resume_hash = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
    cached = session_model.get_report_cache(session_id)
    # Name is parsed locally and passed in only so it can be redacted out of
    # anything sent to the LLM provider.
    candidate_name = (ats.get("parsing", {}).get("contact", {}) or {}).get("name")
    if cached.get("resume_hash") == resume_hash and cached.get("report"):
        report = cached["report"]
    else:
        report = analysis_service.resume_report(resume_text, candidate_name=candidate_name)
        session_model.set_report_cache(session_id, resume_hash, report)

    # Optional JD fit (#2) - retrieve the resume sections most relevant to the JD.
    role_fit = None
    if jd_text:
        retrieval_service.ensure_index(session_id)
        matched = retrieval_service.retrieve(session_id, jd_text, k=4)
        matched_texts = [m["chunk_text"] for m in matched]
        role_fit = analysis_service.jd_fit(
            jd_text, matched_texts, resume_text, candidate_name=candidate_name
        )

    return jsonify({
        "session_id": session_id,
        "ats": ats,
        "suggested_level": report.get("suggested_level", "Junior"),
        "weak_claims": report.get("weak_claims", []),
        "company_fit": report.get("company_fit", {}),
        "role_fit": role_fit,
    })
