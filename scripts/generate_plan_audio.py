#!/usr/bin/env python3
"""
Generate daily MP3s for a reading plan.
Usage:
  python scripts/generate_plan_audio.py chronological-1year -o output/
  python scripts/generate_plan_audio.py ninety-day-challenge -o output/ --speech-volume 4
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# plan_id -> Chinese name pattern
PLAN_FILENAME = {
    "chronological-1year": "历史读经第{i}天",
    "chronological-90days": "90天历史读经第{i}天",
}
PLANS_DIR = REPO_ROOT / "assets" / "bible" / "plans"
CONCAT_SCRIPT = REPO_ROOT / "scripts" / "concat_daily.py"


def main():
    parser = argparse.ArgumentParser(description="Generate daily MP3s from a reading plan")
    parser.add_argument("plan_id", help="Plan ID (e.g. chronological-1year)")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument("--speech-volume", type=int, default=4,
                        help="Boost speech volume in dB (Everest is quiet, default 4)")
    parser.add_argument("--bgm", action="store_true", help="Add background music")
    parser.add_argument("--bgm-volume", type=int, default=-20)
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed (e.g. 2.0 = 2x)")
    parser.add_argument("--start-date", type=str, default="2026-02-17",
                        help="First day date YYYY-MM-DD")
    parser.add_argument("--start-day", type=int, default=1)
    parser.add_argument("--end-day", type=int, default=None)
    args = parser.parse_args()

    plan_path = PLANS_DIR / f"{args.plan_id}.json"
    if not plan_path.exists():
        print(f"Plan not found: {plan_path}")
        print(f"Available: {[p.stem for p in PLANS_DIR.glob('*.json')]}")
        return 1

    plan = json.loads(plan_path.read_text())
    entries = plan["entries"]
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    start_date = date.fromisoformat(args.start_date)
    name_fmt = PLAN_FILENAME.get(args.plan_id, "读经第{i}天")
    start = args.start_day
    end = args.end_day or max(e["day"] for e in entries)

    for entry in entries:
        day = entry["day"]
        if day < start or day > end:
            continue
        chapters = entry.get("chapters", [])
        if not chapters:
            print(f"Day {day}: skip (no chapters)")
            continue
        spec = ",".join(chapters)
        d = start_date + timedelta(days=day - 1)
        prefix = d.strftime("%Y%m%d")  # YYYYMMDD
        name = f"{prefix}_{name_fmt.format(i=day)}"
        if args.bgm:
            name += "-bgm"
        out_file = out_dir / f"{name}.mp3"
        cmd = [
            sys.executable, str(CONCAT_SCRIPT),
            "-c", spec,
            "-o", str(out_file),
            "--speech-volume", str(args.speech_volume),
        ]
        if args.bgm:
            cmd.extend(["--bgm", "--bgm-volume", str(args.bgm_volume)])
        if args.speed > 1.0:
            cmd.extend(["--speed", str(args.speed)])
        subprocess.run(cmd, check=True)
        print(f"Day {day}: {out_file.name}")

    print(f"Done. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
