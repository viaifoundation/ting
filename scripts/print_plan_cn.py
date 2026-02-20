#!/usr/bin/env python3
"""Print reading plan content in Chinese."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_utils import BOOK_CHINESE, load_plan


def chapters_to_chinese(chapters: list[str]) -> str:
    """Convert ['1:1','1:2','1:3'] -> '创世记1-3' or '创世记1、2、3'."""
    if not chapters:
        return ""
    # Group consecutive same-book chapters
    parts = []
    i = 0
    while i < len(chapters):
        book_ch, ch_num = chapters[i].split(":")
        book_num = int(book_ch)
        ch_nums = [int(ch_num)]
        j = i + 1
        while j < len(chapters):
            b, c = chapters[j].split(":")
            if int(b) == book_num and int(c) == ch_nums[-1] + 1:
                ch_nums.append(int(c))
                j += 1
            else:
                break
        i = j
        name = BOOK_CHINESE[book_num] if book_num < len(BOOK_CHINESE) else str(book_num)
        if len(ch_nums) == 1:
            parts.append(f"{name}{ch_nums[0]}")
        elif ch_nums == list(range(ch_nums[0], ch_nums[-1] + 1)):
            parts.append(f"{name}{ch_nums[0]}-{ch_nums[-1]}")
        else:
            parts.append(f"{name}" + "、".join(str(c) for c in ch_nums))
    return "；".join(parts)


def main():
    plan_id = sys.argv[1] if len(sys.argv) > 1 else "chronological-1year"
    max_days = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    start_date = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2026, 2, 17)

    plan_path = Path(__file__).resolve().parent.parent / "asset" / "bible" / "plans" / f"{plan_id}.json"
    if not plan_path.exists():
        print(f"Plan not found: {plan_id}")
        return 1

    plan = load_plan(plan_path)
    plan_name_cn = {"chronological-1year": "历史读经", "chronological-90days": "90天历史读经"}.get(plan_id, plan["name"])
    print(f"【{plan_name_cn}】开始日期：{start_date}\n")

    for entry in plan["entries"][:max_days]:
        day = entry["day"]
        d = start_date + timedelta(days=day - 1)
        chapters = entry.get("chapters", [])
        cn = chapters_to_chinese(chapters)
        print(f"第{day}天（{d}）：{cn}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
