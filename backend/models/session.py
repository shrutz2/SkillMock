"""Session model - one row per uploaded resume / interview session."""
import hmac
import json
import secrets
from datetime import datetime, timedelta

from db.database import execute


def create(resume_filename, parse_meta=None, session_token=None):
    return execute(
        """INSERT INTO sessions (resume_filename, created_at, parse_meta, session_token)
           VALUES (%s, %s, %s, %s)""",
        (
            resume_filename,
            datetime.utcnow().isoformat(timespec="seconds"),
            json.dumps(parse_meta) if parse_meta is not None else None,
            session_token,
        ),
        commit=True,
    )


def new_token():
    """256 bits of CSPRNG entropy - not guessable or enumerable."""
    return secrets.token_urlsafe(32)


def token_matches(session_id, provided_token):
    """Constant-time comparison of a caller's token against the stored one."""
    row = get(session_id)
    if not row:
        return False
    stored = row.get("session_token")
    if not stored:
        # Legacy session created before tokens existed; no owner to verify.
        return False
    return hmac.compare_digest(str(stored), str(provided_token or ""))


def purge(session_id):
    """Delete a session and everything derived from it."""
    removed = 0
    execute(
        """DELETE FROM answers WHERE question_id IN
           (SELECT id FROM (SELECT id FROM questions WHERE session_id = %s) AS q)""",
        (session_id,), commit=True,
    )
    for stmt in (
        "DELETE FROM questions WHERE session_id = %s",
        "DELETE FROM resume_chunks WHERE session_id = %s",
        "DELETE FROM sessions WHERE id = %s",
    ):
        execute(stmt, (session_id,), commit=True)
        removed += 1
    return removed


def purge_older_than(days):
    """Retention job: drop sessions past the retention window."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    rows = execute(
        "SELECT id FROM sessions WHERE created_at < %s", (cutoff,), fetchall=True
    ) or []
    for r in rows:
        purge(r["id"])
    return len(rows)


def get_report_cache(session_id):
    """Return {'resume_hash': ..., 'report': {...}} for this session, or {}."""
    row = get(session_id)
    if not row or not row.get("report_cache"):
        return {}
    try:
        return json.loads(row["report_cache"])
    except Exception:
        return {}


def set_report_cache(session_id, resume_hash, report):
    execute(
        "UPDATE sessions SET report_cache = %s WHERE id = %s",
        (json.dumps({"resume_hash": resume_hash, "report": report}), session_id),
        commit=True,
    )


def get_parse_meta(session_id):
    row = get(session_id)
    if not row or not row.get("parse_meta"):
        return {}
    try:
        return json.loads(row["parse_meta"])
    except Exception:
        return {}


def get(session_id):
    return execute(
        "SELECT * FROM sessions WHERE id = %s", (session_id,), fetchone=True
    )
