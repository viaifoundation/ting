#!/usr/bin/env python3
"""
Regenerate assets/bible/plans/wisdom-praise-{30,45,60,90}days.json.

Rules:
  - Every day includes at least one Psalm chapter and at least one Proverbs chapter.
  - All 150 Psalms are read exactly once, in order.
  - Proverbs: for plans of 31 days or fewer, chapters 1–31 are assigned in order (one day
    may have two chapters when days == 30). For plans longer than 31 days, each day reads
    exactly one Proverbs chapter, cycling 1→31→1… (same idea as multi-month “wisdom” plans
    that revisit Proverbs).

Run from repo root:
  python scripts/build_wisdom_praise_plans.py
"""

from __future__ import annotations

import json
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
    """Split `total` into `days` non-negative counts differing by at most 1 (extras on last days)."""
    if days < 1:
        raise ValueError("days must be >= 1")
    if total < 0:
        raise ValueError("total must be non-negative")
    base, rem = divmod(total, days)
    return [base + (1 if i >= days - rem else 0) for i in range(days)]


def psalm_counts_min_one_per_day(days: int) -> list[int]:
    """All 150 psalms, sequential, at least one per day. Extras spread on later days."""
    if days > 150:
        raise ValueError("Cannot assign 150 psalms with ≥1/day when days > 150")
    if days < 1:
        raise ValueError("days must be >= 1")
    extra_total = 150 - days
    extras = distribute(extra_total, days)
    return [1 + e for e in extras]


def build_entries(days: int) -> list[dict]:
    ps_counts = psalm_counts_min_one_per_day(days)
    ps_next = 1
    entries: list[dict] = []

    if days <= 31:
        # Sequential Proverbs 1..31, ≥1 per day
        extra_pr = 31 - days
        pr_extras = distribute(extra_pr, days)
        pr_counts = [1 + e for e in pr_extras]
        pr_next = 1
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
    else:
        for d in range(1, days + 1):
            i = d - 1
            chapters = []
            for _ in range(ps_counts[i]):
                chapters.append(f"{PSALMS}:{ps_next}")
                ps_next += 1
            prov_ch = ((d - 1) % 31) + 1
            chapters.append(f"{PROVERBS}:{prov_ch}")
            entries.append({"day": d, "chapters": chapters})
        assert ps_next == 151, ps_next

    return entries


def plan_stats(days: int) -> tuple[list[int], float, int]:
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
            "source": "ting/scripts/build_wisdom_praise_plans.py (daily Psalms + Proverbs; Proverbs cycle if n>31)",
            "entries": build_entries(n),
        }
        path = OUT_DIR / f"{meta['id']}.json"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts, mean_ch, max_ch = plan_stats(n)
        print(f"Wrote {path.name}: max {max_ch} chapters/day, mean {mean_ch:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
