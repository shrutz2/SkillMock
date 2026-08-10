"""Thin database abstraction supporting MySQL (architecture spec) and SQLite (demo).

Queries are written once using MySQL-style ``%s`` placeholders; for SQLite the
placeholders are rewritten to ``?`` transparently. This keeps the models simple
while honouring the architecture's MySQL schema.
"""
import sqlite3
import threading

from config import Config

_local = threading.local()


# ----------------------------------------------------------------------------
# Connection handling
# ----------------------------------------------------------------------------
def _connect():
    if Config.DB_BACKEND == "mysql":
        import mysql.connector

        return mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            # autocommit so each connection's reads always see the latest
            # committed rows (avoids REPEATABLE-READ stale snapshots across the
            # per-thread connections used by the threaded dev server).
            autocommit=True,
        )
    conn = sqlite3.connect(Config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn():
    """Return a per-thread connection (Flask dev server is threaded)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


def _adapt(query):
    return query if Config.DB_BACKEND == "mysql" else query.replace("%s", "?")


def execute(query, params=None, *, fetchone=False, fetchall=False, commit=False):
    """Run a query and optionally fetch results / commit.

    Returns fetched rows (as dicts) when requested, otherwise ``lastrowid``.
    """
    conn = get_conn()
    params = params or ()
    if Config.DB_BACKEND == "mysql":
        cur = conn.cursor(dictionary=True)
    else:
        cur = conn.cursor()

    try:
        cur.execute(_adapt(query), params)

        result = None
        if fetchone:
            row = cur.fetchone()
            result = _to_dict(row, cur)
        elif fetchall:
            rows = cur.fetchall()
            result = [_to_dict(r, cur) for r in rows]
        else:
            result = cur.lastrowid

        if commit:
            conn.commit()
        return result
    finally:
        cur.close()


def _to_dict(row, cur):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    # sqlite3.Row -> dict
    return {k: row[k] for k in row.keys()}


# ----------------------------------------------------------------------------
# Schema bootstrap (idempotent) - mirrors db/schema.sql
# ----------------------------------------------------------------------------
_SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_filename TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS resume_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        chunk_text TEXT,
        chunk_index INTEGER,
        faiss_vector_id INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )""",
    """CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        question_text TEXT,
        source_chunk_id INTEGER,
        created_at TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(id),
        FOREIGN KEY (source_chunk_id) REFERENCES resume_chunks(id)
    )""",
    """CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        answer_text TEXT,
        specificity_score REAL,
        feedback_text TEXT,
        created_at TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )""",
]

_MYSQL_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS sessions (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        resume_filename VARCHAR(255),
        created_at DATETIME
    )""",
    """CREATE TABLE IF NOT EXISTS resume_chunks (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        session_id BIGINT,
        chunk_text TEXT,
        chunk_index INT,
        faiss_vector_id INT,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )""",
    """CREATE TABLE IF NOT EXISTS questions (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        session_id BIGINT,
        question_text TEXT,
        source_chunk_id BIGINT,
        created_at DATETIME,
        FOREIGN KEY (session_id) REFERENCES sessions(id),
        FOREIGN KEY (source_chunk_id) REFERENCES resume_chunks(id)
    )""",
    """CREATE TABLE IF NOT EXISTS answers (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        question_id BIGINT,
        answer_text TEXT,
        specificity_score FLOAT,
        feedback_text TEXT,
        created_at DATETIME,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )""",
]


def init_db():
    conn = get_conn()
    schema = _MYSQL_SCHEMA if Config.DB_BACKEND == "mysql" else _SQLITE_SCHEMA
    cur = conn.cursor()
    for stmt in schema:
        cur.execute(stmt)

    # Additive migrations (safe to re-run; each fails harmlessly if present).
    for stmt in (
        # PDF-level ATS diagnostics as JSON.
        "ALTER TABLE sessions ADD COLUMN parse_meta TEXT",
        # Resume report cached per session, keyed by a hash of the resume text,
        # so the same resume always yields the same analysis (and we don't burn
        # an LLM call on every request).
        "ALTER TABLE sessions ADD COLUMN report_cache TEXT",
        # Unguessable token proving ownership of a session. Session ids are
        # sequential, so the id alone must never grant access to the data.
        "ALTER TABLE sessions ADD COLUMN session_token VARCHAR(64)",
    ):
        try:
            cur.execute(stmt)
        except Exception:
            pass  # column already exists

    conn.commit()
    cur.close()
