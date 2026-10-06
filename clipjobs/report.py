"""結果を Markdown / CSV に書き出し、Discord に通知する。"""

from __future__ import annotations

import csv
import json
import re
import urllib.request
from pathlib import Path

from .models import Draft, Job


def _slug(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text)[:40]


def draft_markdown(rank: int, job: Job, draft: Draft) -> str:
    questions = "\n".join(f"- {q}" for q in draft.questions)
    flags = "、".join(job.red_flags) or "なし"
    return f"""# {rank}. {job.title}

- スコア: {job.score:.0f}　/　推定報酬: {f"{job.budget_yen:,}円" if job.budget_yen else "不明"}　/　出どころ: {job.source}
- URL: {job.url or "なし"}
- 注意ワード: {flags}
- 採点の内訳: {"、".join(job.reasons)}
- ID: `{job.id}`

## 応募文

{draft.application}

## 提案単価

{draft.proposed_price}

## 受注前に確認すること

{questions}

## 連絡メール

件名: {draft.email_subject}

{draft.email_body}

## メモ

{draft.notes}

---

<details><summary>募集本文</summary>

{job.body}

</details>
"""


def write(out_dir: Path, results: list[tuple[Job, Draft]]) -> Path:
    drafts_dir = out_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    index = ["# 今日の候補案件", "", "| # | スコア | 報酬 | タイトル | 下書き |", "|---|---|---|---|---|"]
    with open(out_dir / "jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "score", "budget_yen", "title", "url", "source", "red_flags", "id"])
        for i, (job, draft) in enumerate(results, 1):
            name = f"{i:02d}_{_slug(job.title)}.md"
            (drafts_dir / name).write_text(draft_markdown(i, job, draft), encoding="utf-8")
            budget = f"{job.budget_yen:,}円" if job.budget_yen else "-"
            title = job.title.replace("|", "｜")
            index.append(f"| {i} | {job.score:.0f} | {budget} | {title} | [開く](drafts/{name}) |")
            writer.writerow([i, job.score, job.budget_yen or "", job.title, job.url, job.source, " ".join(job.red_flags), job.id])
    (out_dir / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return out_dir


def notify_discord(webhook_url: str, results: list[tuple[Job, Draft]], out_dir: Path) -> None:
    if not webhook_url or not results:
        return
    lines = [f"**切り抜き案件 {len(results)}件** （下書き: `{out_dir}`）"]
    for i, (job, _) in enumerate(results[:10], 1):
        budget = f"{job.budget_yen:,}円" if job.budget_yen else "報酬不明"
        lines.append(f"{i}. [{job.score:.0f}点] {job.title[:60]}（{budget}） {job.url}")
    body = json.dumps({"content": "\n".join(lines)[:1900]}).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[notify] Discord 通知に失敗: {e}")
