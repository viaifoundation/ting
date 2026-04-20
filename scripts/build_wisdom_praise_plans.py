#!/usr/bin/env python3
"""
Regenerate assets/bible/plans/wisdom-praise-{30,45,60,90}days.json.

Each plan covers all 150 Psalms + 31 Proverbs. Chapters are assigned per day
using even remainder distribution (same scheme as the classic 30-day layout:
N psalm chapters then M proverb chapters per day).

Run from repo root:
  python scripts/build_wisdom_praise_plans.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "bible" / "plans"

PSALMS = 19
PROVERBS = 20

META = {
    30: {
        "id": "wisdom-praise-30days",
        "name": "Wisdom & Praise in 30 Days",
        "name_zh": "30天智慧赞美读经计划",
        "name_zh_tw": "30天智慧讚美讀經計劃",
    },
    45: {
        "id": "wisdom-praise-45days",
        "name": "Wisdom & Praise in 45 Days",
        "name_zh": "45天智慧赞美读经计划",
        "name_zh_tw": "45天智慧讚美讀經計劃",
    },
    60: {
        "id": "wisdom-praise-60days",
        "name": "Wisdom & Praise in 60 Days",
        "name_zh": "60天智慧赞美读经计划",
        "name_zh_tw": "60天智慧讚美讀經計劃",
    },
    90: {
        "id": "wisdom-praise-90days",
        "name": "Wisdom & Praise in 90 Days",
        "name_zh": "90天智慧赞美读经计划",
        "name_zh_tw": "90天智慧讚美讀經計劃",
    },
}


def distribute(total: int, days: int) -> list[int]:
    """Split `total` into `days` counts differing by at most 1 (extras on last days)."""
    if days < 1:
        raise ValueError("days must be >= 1")
    base, rem = divmod(total, days)
    # e.g. 31 proverbs / 30 days → one extra on day 30 only (not day 1)
    return [base + (1 if i >= days - rem else 0) for i in range(days)]


def build_entries(days: int) -> list[dict]:
    ps_counts = distribute(150, days)
    pr_counts = distribute(31, days)
    ps_next, pr_next = 1, 1
    entries = []
    for d in range(1, days + 1):
        i = d - 1
        chapters: list[str] = []
        for _ in range(ps_counts[i]):
            chapters.append(f"{PSALMS}:{ps_next}")
            ps_next += 1
        for _ in range(pr_counts[i]):
            chapters.append(f"{PROVERBS}:{pr_next}")
            pr_next += 1
        entries.append({"day": d, "chapters": chapters})
    assert ps_next == 151, ps_next
    assert pr_next == 32, pr_next
    return entries


def plan_stats(days: int) -> tuple[list[int], float, int]:
    """Returns per-day chapter counts, mean, max."""
    ent = build_entries(days)
    counts = [len(e["chapters"]) for e in ent]
    return counts, sum(counts) / days, max(counts)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for n in (30, 45, 60, 90):
        meta = META[n]
        plan = {
            **meta,
            "days": n,
            "source": "ting/scripts/build_wisdom_praise_plans.py",
            "entries": build_entries(n),
        }
        path = OUT_DIR / f"{meta['id']}.json"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts, mean_ch, max_ch = plan_stats(n)
        print(f"Wrote {path.name}: max {max_ch} chapters/day, mean {mean_ch:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
