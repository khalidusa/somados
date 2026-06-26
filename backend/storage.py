import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "results.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            subreddit TEXT NOT NULL,
            sample_size INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def create_job(subreddit: str, sample_size: int) -> str:
    job_id = str(uuid.uuid4())
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id, subreddit, sample_size, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (job_id, subreddit, sample_size, datetime.utcnow().isoformat()),
        )
    return job_id


def set_job_running(job_id: str) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job_id,))


def save_result(job_id: str, result: dict) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='done', result=? WHERE id=?",
            (json.dumps(result), job_id),
        )


def save_error(job_id: str, error: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='error', error=? WHERE id=?",
            (error, job_id),
        )


def get_job(job_id: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("result"):
        d["result"] = json.loads(d["result"])
    return d
