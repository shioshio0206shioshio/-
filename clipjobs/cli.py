"""使い方:

  python -m clipjobs run                  # 集める → 採点 → 下書き作成 → 通知
  python -m clipjobs run --no-llm         # LLM を使わずテンプレートで下書き
  python -m clipjobs draft 募集.txt       # 手元の募集文1件だけ下書きを作る（- で標準入力）
  python -m clipjobs mark <ID> applied    # 応募済み・見送りなどを記録
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

from . import drafting, report, scoring
from .llm import make_backend
from .sources import mail, manual, rss
from .store import Store


def load_yaml(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"{path} がありません。{path.stem}.example.yaml をコピーして作ってください。")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def collect(cfg: dict) -> list:
    src = cfg.get("sources", {})
    jobs = []
    if src.get("rss"):
        jobs += rss.fetch(src["rss"])
    if src.get("mail", {}).get("enabled"):
        jobs += mail.fetch(src["mail"], days=src["mail"].get("days", 2))
    jobs += manual.fetch(Path(src.get("inbox", "inbox")))
    return jobs


def cmd_run(args, cfg: dict, profile: dict) -> None:
    store = Store(Path(cfg.get("db", "data/jobs.sqlite3")))
    jobs = collect(cfg)
    new = []
    for job in jobs:
        if store.is_new(job) and job.id not in {j.id for j in new}:
            new.append(job)
    ranked = scoring.rank(new, cfg.get("scoring", {}))
    limit = args.limit or cfg.get("max_drafts", 10)
    print(f"取得 {len(jobs)}件 / 新着 {len(new)}件 / 条件を満たす {len(ranked)}件 / 下書き {min(limit, len(ranked))}件")

    backend = None if args.no_llm else make_backend(cfg.get("llm", {}))
    results = []
    for job in ranked[:limit]:
        results.append((job, drafting.make_draft(job, profile, backend)))

    for job in new:  # 条件外の案件も記録して次回以降は無視する
        store.add(job)

    if not results:
        return
    out_dir = report.write(Path(cfg.get("output_dir", "out")) / datetime.now().strftime("%Y-%m-%d_%H%M"), results)
    print(f"下書きを書き出しました: {out_dir / 'README.md'}")
    webhook = os.environ.get(cfg.get("notify", {}).get("discord_webhook_env", "CLIPJOBS_DISCORD_WEBHOOK"), "")
    report.notify_discord(webhook, results, out_dir)


def cmd_draft(args, cfg: dict, profile: dict) -> None:
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    job = scoring.score_job(manual.parse_text(text), cfg.get("scoring", {}))
    backend = None if args.no_llm else make_backend(cfg.get("llm", {}))
    print(report.draft_markdown(1, job, drafting.make_draft(job, profile, backend)))


def cmd_mark(args, cfg: dict, profile: dict) -> None:
    store = Store(Path(cfg.get("db", "data/jobs.sqlite3")))
    print("更新しました" if store.set_status(args.id, args.status) else "その ID は見つかりません")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="clipjobs", description="切り抜き動画案件の収集と応募文の下書き")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--profile", default="profile.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="案件を集めて下書きを作る")
    p_run.add_argument("--no-llm", action="store_true")
    p_run.add_argument("--limit", type=int)
    p_run.set_defaults(func=cmd_run)

    p_draft = sub.add_parser("draft", help="募集文1件から下書きを作る")
    p_draft.add_argument("file", help="募集文のテキストファイル（- で標準入力）")
    p_draft.add_argument("--no-llm", action="store_true")
    p_draft.set_defaults(func=cmd_draft)

    p_mark = sub.add_parser("mark", help="案件の状態を記録する")
    p_mark.add_argument("id")
    p_mark.add_argument("status", choices=["applied", "skipped", "won", "lost"])
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args(argv)
    cfg = load_yaml(Path(args.config))
    profile = load_yaml(Path(args.profile)) if args.command != "mark" else {}
    args.func(args, cfg, profile)


if __name__ == "__main__":
    main()
