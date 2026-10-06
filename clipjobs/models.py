from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Job:
    """どのソースから来ても同じ形に揃えた募集1件。"""

    source: str
    title: str
    url: str = ""
    body: str = ""
    posted_at: str = ""

    # スコアリングで埋まる
    score: float = 0.0
    budget_yen: int | None = None
    reasons: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    excluded: bool = False

    @property
    def id(self) -> str:
        key = self.url or f"{self.title}\n{self.body[:500]}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.body}"


@dataclass
class Draft:
    """応募文・メールの下書き。送信は必ず人が確認してから行う。"""

    application: str
    email_subject: str
    email_body: str
    questions: list[str]
    proposed_price: str
    notes: str = ""
