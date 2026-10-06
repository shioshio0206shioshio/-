"""inbox/ フォルダに置いたテキストを募集として取り込む。

Xの募集ポストや DM、サイトの募集ページを見つけたら本文をコピーして
inbox/好きな名前.txt に貼るだけ。1行目がタイトル、URLがあれば自動で拾う。
処理したファイルは inbox/done/ に移動する。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Job

_URL = re.compile(r"https?://\S+")


def parse_text(text: str, source: str = "manual") -> Job:
    lines = [l.strip() for l in text.strip().splitlines()]
    title = next((l for l in lines if l and not _URL.fullmatch(l)), "（タイトルなし）")
    m = _URL.search(text)
    return Job(source=source, title=title, url=m.group(0) if m else "", body=text.strip())


def fetch(inbox: Path, move_done: bool = True) -> list[Job]:
    if not inbox.exists():
        return []
    jobs = []
    for path in sorted(inbox.glob("*.txt")):
        jobs.append(parse_text(path.read_text(encoding="utf-8"), f"manual:{path.name}"))
        if move_done:
            done = inbox / "done"
            done.mkdir(exist_ok=True)
            path.rename(done / path.name)
    return jobs
