"""募集にスコアをつけ、怪しい案件（情報商材・初期費用系）を弾く。"""

from __future__ import annotations

import re
import unicodedata

from .models import Job

_YEN = re.compile(r"(\d+(?:\.\d+)?)\s*(万)?\s*円")


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace(",", "")


def parse_budget_yen(text: str) -> int | None:
    """本文中の金額のうち最大のものを返す（「1本1,500円」「3万円」など）。"""
    amounts = []
    for num, man in _YEN.findall(normalize(text)):
        value = float(num) * (10000 if man else 1)
        amounts.append(int(value))
    return max(amounts) if amounts else None


def score_job(job: Job, cfg: dict) -> Job:
    text = normalize(job.text)
    job.score, job.reasons, job.red_flags = 0.0, [], []

    for word in cfg.get("exclude_keywords", []):
        if re.search(normalize(word), text, re.IGNORECASE):
            job.excluded = True
            job.reasons.append(f"除外ワード「{word}」")

    for word, points in cfg.get("include_keywords", {}).items():
        if re.search(normalize(word), text, re.IGNORECASE):
            job.score += points
            job.reasons.append(f"+{points} {word}")

    for pattern, points in cfg.get("red_flags", {}).items():
        if re.search(normalize(pattern), text, re.IGNORECASE):
            job.score += points
            job.red_flags.append(pattern)

    job.budget_yen = parse_budget_yen(text)
    min_budget = cfg.get("min_budget_yen", 0)
    if job.budget_yen is None:
        job.reasons.append("報酬の記載なし")
    elif job.budget_yen < min_budget:
        job.score -= 20
        job.reasons.append(f"-20 報酬が下限未満（{job.budget_yen:,}円）")
    else:
        bonus = min(30, job.budget_yen // cfg.get("yen_per_point", 1000))
        job.score += bonus
        job.reasons.append(f"+{bonus} 報酬 {job.budget_yen:,}円")

    if len(job.red_flags) >= cfg.get("max_red_flags", 2):
        job.excluded = True
    return job


def rank(jobs: list[Job], cfg: dict) -> list[Job]:
    scored = [score_job(j, cfg) for j in jobs]
    threshold = cfg.get("min_score", 0)
    keep = [j for j in scored if not j.excluded and j.score >= threshold]
    return sorted(keep, key=lambda j: j.score, reverse=True)
