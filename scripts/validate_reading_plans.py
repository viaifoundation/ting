#!/usr/bin/env python3
"""
Validate assets/bible/plans/*.json: structure, day coverage, chapter refs (Protestant 66-book).

Exit 1 if any ERROR; prints WARN for minor issues.

Usage (repo root):
  python scripts/validate_reading_plans.py
  python scripts/validate_reading_plans.py --plan wisdom-praise-90days
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANS_DIR = REPO_ROOT / "assets" / "bible" / "plans"

# Max chapter count per book (index 0 unused; index 1 = Genesis … 66 = Revelation)
_BOOK_CHAPTER_COUNTS = (
    50,
    40,
    27,
    36,
    34,
    24,
    21,
    4,
    31,
    24,
    22,
    25,
    29,
    36,
    10,
    13,
    10,
    42,
    150,
    31,
    12,
    8,
    66,
    52,
    5,
    48,
    12,
    14,
    3,
    9,
    1,
    4,
    7,
    3,
    3,
    3,
    2,
    14,
    4,
    28,
    16,
    24,
    21,
    28,
    16,
    16,
    13,
    6,
    6,
    4,
    4,
    5,
    3,
    6,
    4,
    3,
    1,
    13,
    5,
    5,
    3,
    5,
    1,
    1,
    1,
    22,
)
assert len(_BOOK_CHAPTER_COUNTS) == 66
BOOK_MAX_CHAPTER: tuple[int, ...] = (0,) + _BOOK_CHAPTER_COUNTS

# Plans where calendar day 1..meta_days is NOT expected (catch-up gaps, etc.)
GAPPED_CALENDAR_PLANS = frozenset({"stay-on-track"})

# meta["days"] may differ from len(entries) for these (documented)
ALLOW_ENTRY_COUNT_MISMATCH = frozenset({"stay-on-track"})


def parse_chapter_ref(s: str) -> tuple[int, int] | None:
    s = s.strip()
    if not re.fullmatch(r"\d+:\d+", s):
        return None
    b, c = s.split(":", 1)
    return int(b), int(c)


def validate_chapter_ref(plan_id: str, day: int, ref: str) -> list[str]:
    errs: list[str] = []
    parsed = parse_chapter_ref(ref)
    if parsed is None:
        errs.append(f"{plan_id} day {day}: bad chapter ref {ref!r} (want book:chapter)")
        return errs
    b, c = parsed
    if b < 1 or b > 66:
        errs.append(f"{plan_id} day {day}: book {b} out of range 1-66 in {ref}")
        return errs
    mx = BOOK_MAX_CHAPTER[b]
    if c < 1 or c > mx:
        errs.append(f"{plan_id} day {day}: {ref} — chapter {c} invalid (max {mx} for book {b})")
    return errs


def validate_wisdom_praise(plan_id: str, data: dict) -> list[str]:
    """All 150 Psalms exactly once; each day has Psalm + Proverbs."""
    errs: list[str] = []
    psalms: list[int] = []
    for e in data["entries"]:
        day = e["day"]
        chs = e.get("chapters") or []
        has_ps = any(x.startswith("19:") for x in chs)
        has_pr = any(x.startswith("20:") for x in chs)
        if not has_ps:
            errs.append(f"{plan_id} day {day}: missing Psalm (book 19)")
        if not has_pr:
            errs.append(f"{plan_id} day {day}: missing Proverbs (book 20)")
        for x in chs:
            if x.startswith("19:"):
                try:
                    psalms.append(int(x.split(":", 1)[1]))
                except ValueError:
                    errs.append(f"{plan_id} day {day}: bad psalm ref {x}")
    ctr = Counter(psalms)
    missing = [n for n in range(1, 151) if ctr[n] == 0]
    dupes = [n for n, k in ctr.items() if k > 1]
    if missing:
        errs.append(f"{plan_id}: missing Psalm chapters: {missing[:20]}{'…' if len(missing) > 20 else ''}")
    if dupes:
        errs.append(f"{plan_id}: duplicate Psalm chapters: {sorted(dupes)[:30]}{'…' if len(dupes) > 30 else ''}")
    if sorted(psalms) != list(range(1, 151)):
        errs.append(f"{plan_id}: Psalms set should be 1..150 exactly once (got {len(psalms)} refs)")
    return errs


def validate_psalms_30(plan_id: str, data: dict) -> list[str]:
    errs: list[str] = []
    all_ps: list[int] = []
    for e in data["entries"]:
        chs = e.get("chapters") or []
        if len(chs) != 5:
            errs.append(f"{plan_id} day {e['day']}: expected 5 Psalm chapters, got {len(chs)}")
        for x in chs:
            if not x.startswith("19:"):
                errs.append(f"{plan_id} day {e['day']}: non-Psalm ref {x}")
            else:
                all_ps.append(int(x.split(":", 1)[1]))
    ctr = Counter(all_ps)
    if sorted(all_ps) != list(range(1, 151)):
        errs.append(f"{plan_id}: should cover Psalms 1-150 once each")
    return errs


def validate_nt_pp_90(plan_id: str, data: dict) -> list[str]:
    """NT + Psalms + Proverbs: days 1–60 have 2 Psalms; 61–90 have 1; every day 1 Proverb + ≥1 NT."""
    errs: list[str] = []
    psalms_all: list[int] = []
    for e in data["entries"]:
        day = e["day"]
        chs = e.get("chapters") or []
        nt = []
        for x in chs:
            parsed = parse_chapter_ref(x)
            if not parsed:
                continue
            b, _c = parsed
            if 40 <= b <= 66:
                nt.append(x)
        ps = [x for x in chs if x.startswith("19:")]
        pr = [x for x in chs if x.startswith("20:")]
        exp_ps = 2 if day <= 60 else 1
        if len(ps) != exp_ps:
            errs.append(
                f"{plan_id} day {day}: expected {exp_ps} Psalm ref(s), got {len(ps)}"
            )
        if len(pr) != 1:
            errs.append(f"{plan_id} day {day}: expected 1 Proverbs ref, got {len(pr)}")
        if len(nt) < 1:
            errs.append(f"{plan_id} day {day}: expected at least one NT chapter")
        for x in ps:
            try:
                psalms_all.append(int(x.split(":")[1]))
            except ValueError:
                errs.append(f"{plan_id} day {day}: bad psalm {x}")
    ctr = Counter(psalms_all)
    bad_ps = [n for n in range(1, 151) if ctr[n] != 1]
    if bad_ps:
        sample = bad_ps[:15]
        errs.append(
            f"{plan_id}: each Psalm 1–150 should appear once; off: {sample}"
            f"{'…' if len(bad_ps) > 15 else ''}"
        )
    return errs


def validate_plan(path: Path) -> tuple[list[str], list[str]]:
    plan_id = path.stem
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{plan_id}: invalid JSON: {e}"], []

    meta_days = data.get("days")
    entries = data.get("entries")
    if not isinstance(meta_days, int) or meta_days < 1:
        errors.append(f"{plan_id}: missing or invalid 'days'")
    if not isinstance(entries, list) or not entries:
        errors.append(f"{plan_id}: missing or empty 'entries'")
        return errors, warnings

    if plan_id not in ALLOW_ENTRY_COUNT_MISMATCH and len(entries) != meta_days:
        errors.append(
            f"{plan_id}: len(entries)={len(entries)} != days={meta_days}"
        )

    days_seen: set[int] = set()
    for e in entries:
        if not isinstance(e, dict):
            errors.append(f"{plan_id}: entry is not an object: {e!r}")
            continue
        day = e.get("day")
        if not isinstance(day, int):
            errors.append(f"{plan_id}: entry missing int day: {e!r}")
            continue
        if day in days_seen:
            errors.append(f"{plan_id}: duplicate day {day}")
        days_seen.add(day)
        chs = e.get("chapters")
        if not isinstance(chs, list):
            errors.append(f"{plan_id} day {day}: 'chapters' not a list")
            continue
        if len(chs) == 0:
            errors.append(f"{plan_id} day {day}: empty chapters")

        for ref in chs:
            if not isinstance(ref, str):
                errors.append(f"{plan_id} day {day}: chapter ref not string: {ref!r}")
                continue
            errors.extend(validate_chapter_ref(plan_id, day, ref))

    if plan_id not in GAPPED_CALENDAR_PLANS:
        expected_days = set(range(1, (meta_days or 0) + 1))
        missing = sorted(expected_days - days_seen)
        if missing:
            errors.append(f"{plan_id}: missing day indices: {missing[:40]}{'…' if len(missing) > 40 else ''}")
        extra = sorted(days_seen - expected_days)
        if extra:
            errors.append(f"{plan_id}: unexpected day indices: {extra}")

    # Semantic checks
    if plan_id.startswith("wisdom-praise-"):
        errors.extend(validate_wisdom_praise(plan_id, data))
    if plan_id == "psalms-30days":
        errors.extend(validate_psalms_30(plan_id, data))
    if plan_id == "nt-psalms-proverbs-90days":
        errors.extend(validate_nt_pp_90(plan_id, data))

    if plan_id in GAPPED_CALENDAR_PLANS:
        missing_cal = sorted(set(range(1, meta_days + 1)) - days_seen)
        if missing_cal:
            warnings.append(
                f"{plan_id}: gapped plan — {len(missing_cal)} calendar days have no entry "
                f"(e.g. {missing_cal[:8]}{'…' if len(missing_cal) > 8 else ''})"
            )

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate reading plan JSON files")
    ap.add_argument("--plan", metavar="ID", help="Validate only this plan id (stem name)")
    args = ap.parse_args()

    paths = sorted(PLANS_DIR.glob("*.json"))
    if args.plan:
        paths = [p for p in paths if p.stem == args.plan]
        if not paths:
            print(f"No plan named {args.plan!r} in {PLANS_DIR}", file=sys.stderr)
            return 2

    all_errs: list[str] = []
    all_warn: list[str] = []
    for path in paths:
        errs, warns = validate_plan(path)
        all_errs.extend(errs)
        all_warn.extend(warns)

    for w in all_warn:
        print(f"WARN {w}")
    for e in all_errs:
        print(f"ERROR {e}")

    if not paths:
        print("No JSON plans found.", file=sys.stderr)
        return 2

    print(f"Checked {len(paths)} file(s).")
    if all_errs:
        print(f"Failed: {len(all_errs)} error(s), {len(all_warn)} warning(s).")
        return 1
    print(f"OK — no errors ({len(all_warn)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
