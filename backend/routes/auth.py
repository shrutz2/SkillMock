"""Session ownership check.

Session ids are sequential integers, so the id alone must never be enough to
read a session's data - otherwise anyone can walk 1, 2, 3... and pull every
user's resume, questions and answers. Each upload issues an unguessable token
that the caller must present to touch that session again.
"""
from functools import wraps

from flask import jsonify, request

from models import session as session_model


def provided_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    if request.headers.get("X-Session-Token"):
        return request.headers["X-Session-Token"].strip()
    body = request.get_json(silent=True) or {}
    return (body.get("session_token") or request.args.get("session_token") or "").strip()


def require_session(get_session_id):
    """Guard a route with an ownership check.

    ``get_session_id`` receives the view's kwargs and returns the session id
    being accessed (from the URL or the JSON body).
    """
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            session_id = get_session_id(kwargs)
            if not session_id:
                return jsonify({"error": "session_id is required"}), 400
            if not session_model.get(session_id):
                return jsonify({"error": "Unknown session_id"}), 404
            if not session_model.token_matches(session_id, provided_token()):
                # Same response shape whether the session exists or not, so the
                # endpoint can't be used to probe which ids are valid.
                return jsonify({"error": "Not authorized for this session"}), 403
            return view(*args, **kwargs)
        return wrapper
    return decorator


def session_id_from_body(_kwargs):
    body = request.get_json(silent=True) or {}
    return body.get("session_id")


def session_id_from_url(kwargs):
    return kwargs.get("session_id")
