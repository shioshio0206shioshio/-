"""求人サイトの「新着お知らせメール」を IMAP で読んで募集を取り込む。

サイトへ直接アクセスしないので、規約上いちばん安全な取り込み方。
クラウドワークス／ランサーズなどで検索条件を保存して新着通知メールを有効にしておく。
"""

from __future__ import annotations

import email
import imaplib
import os
import re
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.message import Message

from ..models import Job
from .rss import strip_html

_URL = re.compile(r"https?://[^\s\"'<>）)]+")


def _decode(value: str | None) -> str:
    return str(make_header(decode_header(value))) if value else ""


def message_text(msg: Message) -> str:
    plain, html_part = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/plain" and not plain:
            plain = text
        elif ctype == "text/html" and not html_part:
            html_part = text
    if plain:
        return plain
    # HTML しか無いメールは改行を残してタグを落とす
    html_part = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", html_part)
    return "\n".join(strip_html(line) for line in html_part.splitlines())


def extract_jobs(text: str, url_patterns: list[str], source: str) -> list[Job]:
    """メール本文から募集URLを探し、URLの直前の行をタイトル、直後の数行を本文とみなす。"""
    lines = [line.strip() for line in text.splitlines()]
    patterns = [re.compile(p) for p in url_patterns]
    jobs, seen = [], set()
    for i, line in enumerate(lines):
        for url in _URL.findall(line):
            if not any(p.search(url) for p in patterns) or url in seen:
                continue
            seen.add(url)
            before = line[: line.find(url)].strip(" :：-")
            title = before or next((lines[j] for j in range(i - 1, max(i - 4, -1), -1) if lines[j]), "")
            body = "\n".join(l for l in lines[i + 1 : i + 6] if l and not _URL.search(l))
            jobs.append(Job(source=source, title=title or url, url=url, body=body))
    return jobs


def fetch(cfg: dict, days: int = 2) -> list[Job]:
    host = cfg.get("host", "imap.gmail.com")
    user = os.environ.get(cfg.get("user_env", "CLIPJOBS_IMAP_USER"), "")
    password = os.environ.get(cfg.get("password_env", "CLIPJOBS_IMAP_PASSWORD"), "")
    if not user or not password:
        print("[mail] IMAP のユーザー名／アプリパスワードが環境変数に無いのでスキップ")
        return []

    since = (date.today() - timedelta(days=days)).strftime("%d-%b-%Y")
    jobs: list[Job] = []
    with imaplib.IMAP4_SSL(host) as imap:
        imap.login(user, password)
        imap.select(cfg.get("mailbox", "INBOX"), readonly=True)  # 既読にしない
        for sender in cfg.get("senders", []):
            _, data = imap.search(None, "SINCE", since, "FROM", f'"{sender["from"]}"')
            for num in data[0].split():
                _, msg_data = imap.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                found = extract_jobs(message_text(msg), sender["url_patterns"], sender["name"])
                for job in found:
                    job.posted_at = _decode(msg.get("Date"))
                jobs.extend(found)
    return jobs
