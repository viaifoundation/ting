#!/usr/bin/env python3
"""Print reading plan content in Chinese."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_utils import BOOK_CHINESE, load_plan, chapters_to_chinese


def main():
    plan_id = sys.argv[1] if len(sys.argv) > 1 else "chronological-1year"
    max_days = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    start_date = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2026, 2, 17)

    plan_path = Path(__file__).resolve().parent.parent / "assets" / "bible" / "plans" / f"{plan_id}.json"
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
        cn = chapters_to_chinese(chapters, BOOK_CHINESE)
        print(f"第{day}天（{d}）：{cn}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
