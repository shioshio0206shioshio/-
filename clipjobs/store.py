"""一度見た募集を SQLite に記録して、同じ案件を何度も通知しないようにする。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Job


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, source TEXT, title TEXT, url TEXT,
                score REAL, first_seen TEXT, status TEXT DEFAULT 'new'
            )"""
        )

    def is_new(self, job: Job) -> bool:
        return self.db.execute("SELECT 1 FROM jobs WHERE id = ?", (job.id,)).fetchone() is None

    def add(self, job: Job) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO jobs (id, source, title, url, score, first_seen) VALUES (?, ?, ?, ?, ?, ?)",
            (job.id, job.source, job.title, job.url, job.score, datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()

    def set_status(self, job_id: str, status: str) -> bool:
        cur = self.db.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        self.db.commit()
        return cur.rowcount > 0
