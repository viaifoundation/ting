#!/usr/bin/env python3
"""
Generate new Wisdom & Praise plans:
  1. psalms-proverbs-93days.json (3 months):
     - 4:1 merge of YouVersion 372-day plan
     - 4 Psalms + 4 Proverbs chapters per day
  2. psalms-proverbs-62days.json (2 months):
     - 1:2 split of YouVersion 31-day plan
     - 2-3 Psalms + 1 Proverbs chapter per day (Proverbs cycles 1-31 twice)
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANS_BACKEND_DIR = REPO_ROOT / "assets" / "bible" / "plans"
PLANS_FRONTEND_DIR = Path("/Users/mhuo/github/shema/public/plans")

def main():
    # Ensure directories exist
    PLANS_BACKEND_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════════
    # 1. Generate 93-Day Plan (4:1 Merge of YouVersion 372-Day)
    # ══════════════════════════════════════════════════════════════════════
    yv372_path = PLANS_BACKEND_DIR / "psalms-proverbs-youversion-372.json"
    if not yv372_path.exists():
        print(f"❌ Error: {yv372_path} does not exist.")
        return 1

    with open(yv372_path, "r", encoding="utf-8") as f:
        yv372 = json.load(f)

    yv372_entries = yv372["entries"]
    merged_93_entries = []

    for d in range(1, 94):
        merged_chapters = []
        for offset in range(4):
            idx = (d - 1) * 4 + offset
            merged_chapters.extend(yv372_entries[idx]["chapters"])
        merged_93_entries.append({
            "day": d,
            "chapters": merged_chapters
        })

    plan_93 = {
        "id": "psalms-proverbs-93days",
        "name": "Psalms & Proverbs (93 Days)",
        "name_zh": "3个月智慧赞美计划",
        "name_zh_tw": "3個月智慧讚美計劃",
        "days": 93,
        "source": "Derived from YouVersion Psalms & Proverbs 372-day plan (4:1 merge)",
        "entries": merged_93_entries
    }

    # ══════════════════════════════════════════════════════════════════════
    # 2. Generate 62-Day Plan (1:2 Split of YouVersion 31-Day)
    # ══════════════════════════════════════════════════════════════════════
    yv31_path = PLANS_BACKEND_DIR / "psalms-proverbs-youversion-31.json"
    if not yv31_path.exists():
        print(f"❌ Error: {yv31_path} does not exist.")
        return 1

    with open(yv31_path, "r", encoding="utf-8") as f:
        yv31 = json.load(f)

    yv31_entries = yv31["entries"]
    split_62_entries = []

    for d in range(1, 32):
        entry_31 = yv31_entries[d - 1]
        original_chapters = entry_31["chapters"]
        
        # Separate Psalms and Proverbs
        ps_chapters = [ch for ch in original_chapters if ch.startswith("19:")]
        
        # Split Psalms: 3 on odd day, 2 on even day (except Day 31: Psalm 119 only on Day 62)
        if d == 31:
            odd_ps = []
            even_ps = ps_chapters
        else:
            odd_ps = ps_chapters[:3]
            even_ps = ps_chapters[3:]
            
        odd_day = 2 * d - 1
        even_day = 2 * d
        
        # Cycle Proverbs 1..31 twice (1 chapter per day)
        odd_prov = f"20:{((odd_day - 1) % 31) + 1}"
        even_prov = f"20:{((even_day - 1) % 31) + 1}"
        
        split_62_entries.append({
            "day": odd_day,
            "chapters": odd_ps + [odd_prov]
        })
        split_62_entries.append({
            "day": even_day,
            "chapters": even_ps + [even_prov]
        })

    plan_62 = {
        "id": "psalms-proverbs-62days",
        "name": "Psalms & Proverbs (62 Days)",
        "name_zh": "2个月智慧赞美计划",
        "name_zh_tw": "2個月智慧讚美計劃",
        "days": 62,
        "source": "Derived from YouVersion Psalms & Proverbs 31-day plan (1:2 split)",
        "entries": split_62_entries
    }

    # Write plan files
    for p_id, p_data in [("psalms-proverbs-93days", plan_93), ("psalms-proverbs-62days", plan_62)]:
        # Backend path
        b_path = PLANS_BACKEND_DIR / f"{p_id}.json"
        with open(b_path, "w", encoding="utf-8") as f:
            json.dump(p_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        
        # Frontend path
        f_path = PLANS_FRONTEND_DIR / f"{p_id}.json"
        with open(f_path, "w", encoding="utf-8") as f:
            json.dump(p_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            
        print(f"✅ Wrote {p_id}.json (days={p_data['days']})")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
