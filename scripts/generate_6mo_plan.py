#!/usr/bin/env python3
"""
Generate two 186-day reading plans:

  1. chronological-6month.json  — Chrono reading (半年歷史讀經)
     - 365-day plan merged 2:1 → 183 days
     - Un-merge 2 heaviest days → 185 days
     - Split Ps 119 into own day (Ps 119 + Prov 1 + Prov 31) → 186 days

  2. psalms-proverbs-186days.json — Daily Psalms & Proverbs (智慧讚美)
     - YV-372 merged 2:1 → 186 days (2 Psalms + 2 Proverbs per day)
     - The Ps 119 day is empty (chrono plan already covers it)

Usage:
  python scripts/generate_6mo_plan.py
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANS_DIR = REPO_ROOT / "assets" / "bible" / "plans"


def get_chapter_duration(chapter_ref: str) -> float:
    """Get duration of a chapter audio file in seconds."""
    book, chap = chapter_ref.split(":")
    f = REPO_ROOT / "assets" / "bible" / "audio" / "chapters" / f"{int(book):03d}_{int(chap):03d}.mp3"
    if not f.exists():
        return 0
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0


def get_day_duration(chapters: list[str]) -> float:
    """Total duration of a list of chapter refs."""
    return sum(get_chapter_duration(ch) for ch in chapters)


def generate_plans():
    one_year_path = PLANS_DIR / "chronological-1year.json"
    yv372_path = PLANS_DIR / "psalms-proverbs-youversion-372.json"
    chrono_out = PLANS_DIR / "chronological-6month.json"
    psprov_out = PLANS_DIR / "psalms-proverbs-186days.json"

    with open(one_year_path, "r", encoding="utf-8") as f:
        one_year = json.load(f)
    with open(yv372_path, "r", encoding="utf-8") as f:
        yv372 = json.load(f)

    entries_1yr = one_year["entries"]

    # ══════════════════════════════════════════════════════════════════════
    # PLAN 1: Chronological 6-Month (186 days)
    # ══════════════════════════════════════════════════════════════════════

    # ── Step 1: Merge every 2 consecutive days → 183 base days ────────────
    merged = []
    for i in range(0, len(entries_1yr), 2):
        chapters = list(entries_1yr[i]["chapters"])
        original_pairs = [entries_1yr[i]["chapters"]]
        if i + 1 < len(entries_1yr):
            chapters.extend(entries_1yr[i + 1]["chapters"])
            original_pairs.append(entries_1yr[i + 1]["chapters"])
        merged.append({
            "chapters": chapters,
            "original_pairs": original_pairs,
        })
    print(f"Step 1: Merged 365 → {len(merged)} days")

    # ── Step 2: Split Ps 119 into its own day ─────────────────────────────
    ps119_merged_idx = None
    for idx, entry in enumerate(merged):
        if "19:119" in entry["chapters"]:
            ps119_merged_idx = idx
            break

    assert ps119_merged_idx is not None, "Psalm 119 not found in merged plan!"

    # Remove Ps 119 from the merged day
    merged[ps119_merged_idx]["chapters"] = [
        ch for ch in merged[ps119_merged_idx]["chapters"] if ch != "19:119"
    ]

    # Insert Ps 119 + Prov 1 + Prov 31 as a new day
    ps119_special = {
        "chapters": ["19:119", "20:1", "20:31"],
        "original_pairs": None,
        "is_ps119_day": True,
    }
    merged.insert(ps119_merged_idx + 1, ps119_special)
    print(f"Step 2: Split Ps 119 → {len(merged)} days "
          f"(Ps 119 + Prov 1 + Prov 31 on position {ps119_merged_idx + 2})")

    # ── Step 3: Un-merge 2 heaviest days → 186 ───────────────────────────
    day_durations = []
    for idx, entry in enumerate(merged):
        if entry.get("is_ps119_day"):
            continue
        if entry["original_pairs"] is None or len(entry["original_pairs"]) < 2:
            continue
        dur = get_day_duration(entry["chapters"])
        day_durations.append((idx, dur))

    day_durations.sort(key=lambda x: -x[1])

    # Un-merge top 2 heaviest (process from end to preserve indices)
    unmerge_indices = sorted([day_durations[0][0], day_durations[1][0]], reverse=True)
    for idx in unmerge_indices:
        entry = merged[idx]
        pair_a = entry["original_pairs"][0]
        pair_b = entry["original_pairs"][1]
        print(f"Step 3: Un-merging position {idx + 1} "
              f"({get_day_duration(entry['chapters']) / 60:.1f} min → "
              f"{get_day_duration(pair_a) / 60:.1f} + {get_day_duration(pair_b) / 60:.1f} min)")
        merged[idx:idx + 1] = [
            {"chapters": list(pair_a), "original_pairs": [pair_a]},
            {"chapters": list(pair_b), "original_pairs": [pair_b]},
        ]

    print(f"Step 3: Un-merged 2 heaviest → {len(merged)} days")
    assert len(merged) == 186, f"Expected 186, got {len(merged)}"

    # Find final Ps 119 day number
    ps119_day_num = None
    for i, entry in enumerate(merged):
        if entry.get("is_ps119_day"):
            ps119_day_num = i + 1
            break

    # Build chrono plan JSON
    chrono_entries = []
    for i, entry in enumerate(merged):
        chrono_entries.append({
            "day": i + 1,
            "chapters": entry["chapters"],
        })

    chrono_plan = {
        "id": "chronological-6month",
        "name": "Chronological (6 Months)",
        "name_zh": "半年历史读经",
        "name_zh_tw": "半年歷史讀經",
        "days": 186,
        "ps119_day": ps119_day_num,
        "source": "Derived from Chronological 1-Year plan (2:1 merge, Ps 119 split, 2 heavy days un-merged)",
        "entries": chrono_entries,
    }

    with open(chrono_out, "w", encoding="utf-8") as f:
        json.dump(chrono_plan, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # ══════════════════════════════════════════════════════════════════════
    # PLAN 2: Psalms & Proverbs 186 days (YV-372 merged 2:1)
    # ══════════════════════════════════════════════════════════════════════

    yv_entries = yv372["entries"]
    yv_merged = []
    for i in range(0, len(yv_entries), 2):
        chapters = list(yv_entries[i]["chapters"])
        if i + 1 < len(yv_entries):
            chapters.extend(yv_entries[i + 1]["chapters"])
        yv_merged.append(chapters)

    assert len(yv_merged) == 186, f"Expected 186 YV days, got {len(yv_merged)}"

    psprov_entries = []
    for i, chapters in enumerate(yv_merged):
        day_num = i + 1
        # Ps 119 day in chrono already has Ps+Prov → skip bonus
        if day_num == ps119_day_num:
            psprov_entries.append({"day": day_num, "chapters": []})
        else:
            psprov_entries.append({"day": day_num, "chapters": chapters})

    psprov_plan = {
        "id": "psalms-proverbs-186days",
        "name": "Psalms & Proverbs (186 Days)",
        "name_zh": "半年智慧赞美",
        "name_zh_tw": "半年智慧讚美",
        "days": 186,
        "skip_day": ps119_day_num,
        "source": "Derived from YouVersion Psalms & Proverbs 372-day plan (2:1 merge)",
        "entries": psprov_entries,
    }

    with open(psprov_out, "w", encoding="utf-8") as f:
        json.dump(psprov_plan, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # ══════════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print(f"Generated 2 plans:")
    print(f"  1. {chrono_out.name} — {len(chrono_entries)} days (半年歷史讀經)")
    print(f"  2. {psprov_out.name} — {len(psprov_entries)} days (智慧讚美)")
    print(f"  Ps 119 day: Day {ps119_day_num} (Ps 119 + Prov 1 + Prov 31)")

    # Duration stats
    chrono_durs = [get_day_duration(e["chapters"]) for e in chrono_entries]
    psprov_durs = [get_day_duration(e["chapters"]) for e in psprov_entries if e["chapters"]]

    chrono_avg = sum(chrono_durs) / len(chrono_durs)
    psprov_avg = sum(psprov_durs) / len(psprov_durs) if psprov_durs else 0

    print(f"\n  Chrono avg at 1.5x:  {chrono_avg / 60 / 1.5:.1f} min")
    print(f"  Ps+Prov avg at 1.5x: {psprov_avg / 60 / 1.5:.1f} min")
    print(f"  Combined avg at 1.5x: {(chrono_avg + psprov_avg) / 60 / 1.5:.1f} min")
    print(f"  Chrono max at 1.5x:  {max(chrono_durs) / 60 / 1.5:.1f} min")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    generate_plans()
