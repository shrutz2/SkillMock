"""Per-client rate limiting.

Uploads run an embedding model and the LLM endpoints cost money, so both need a
ceiling. This is an in-process sliding window, which suits a single-instance
deployment; behind multiple workers it would move to Redis.
"""
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

_hits = defaultdict(deque)
_lock = threading.Lock()


def _client_id():
    # Honour a proxy header only for the first hop, then fall back to the peer.
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(limit, window_seconds, scope="default"):
    """Allow ``limit`` requests per ``window_seconds`` per client, per scope."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            key = (scope, _client_id())
            now = time.time()
            with _lock:
                q = _hits[key]
                cutoff = now - window_seconds
                while q and q[0] < cutoff:
                    q.popleft()
                if len(q) >= limit:
                    retry = int(q[0] + window_seconds - now) + 1
                    resp = jsonify({
                        "error": "Too many requests. Please slow down.",
                        "retry_after_seconds": retry,
                    })
                    resp.status_code = 429
                    resp.headers["Retry-After"] = str(retry)
                    return resp
                q.append(now)
            return view(*args, **kwargs)
        return wrapper
    return decorator
