"""Architecture-named entry point for DB access.

The actual implementation lives in ``db.database`` and supports both the MySQL
backend from the architecture doc and a zero-setup SQLite fallback for demos.
"""
from db.database import execute, get_conn, init_db  # noqa: F401
