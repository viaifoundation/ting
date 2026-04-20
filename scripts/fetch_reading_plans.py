#!/usr/bin/env python3
"""
Fetch reading plans from Bible Study Tools and bible.com, save as JSON.
Run from repo root: python scripts/fetch_reading_plans.py

Top 10 popular yearly plans (365 days), ranked by popularity/recognition:
  1. Chronological - events in historical order (Bible Study Tools)
  2. Book Order - Genesis→Revelation in canon order (BST)
  3. Old and New Testament - OT + NT daily (BST)
  4. Classic - 3 readings/day, M'Cheyne-style (BST)
  5. One-Year Immersion - OT once, NT 3× (BST)
  6. Stay-on-Track - catch-up days built in (BST)
  7. The Busy-Life - lighter load (BST)
  8–10. bible.com plans (Chronological 90d, Ninety-Day also available)

Curated YouVersion (bible.com) plans (--youversion): M'Cheyne; Psalms & Proverbs (372d);
Psalms+Proverbs in 31d; Bible in a Year (ABS); Bible in a Year (Ligonier OT+NT).
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

# Add repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_utils import parse_day_text

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANS_DIR = REPO_ROOT / "assets" / "bible" / "plans"

BIBLE_COM_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ting-fetch_reading_plans/1.0)"}

# bible.com reader links use /bible/<version>/<ABBR>.<ch>.<VERSION_CODE>
BIBLE_COM_ABBR_TO_NUM = {
    "GEN": 1, "EXO": 2, "EXOD": 2, "LEV": 3, "NUM": 4, "DEUT": 5, "DEU": 5,
    "JOSH": 6, "JOS": 6, "JDG": 7, "RUTH": 8, "RUT": 8,
    "1SAM": 9, "1SA": 9, "2SAM": 10, "2SA": 10, "1KGS": 11, "1KI": 11, "2KGS": 12, "2KI": 12,
    "1CHR": 13, "1CH": 13, "2CHR": 14, "2CH": 14, "EZRA": 15, "EZR": 15,
    "NEH": 16, "ESTH": 17, "EST": 17, "JOB": 18, "PS": 19, "PSA": 19,
    "PROV": 20, "PRO": 20, "ECCL": 21, "ECC": 21, "SONG": 22, "SNG": 22,
    "ISA": 23, "JER": 24, "LAM": 25, "EZK": 26, "DAN": 27, "HOS": 28,
    "JOEL": 29, "JOL": 29, "AMOS": 30, "AMO": 30, "OBA": 31, "JON": 32,
    "MIC": 33, "NAH": 34, "NAM": 34, "HAB": 35, "ZEP": 36, "HAG": 37,
    "ZEC": 38, "MAL": 39, "MATT": 40, "MAT": 40, "MARK": 41, "MRK": 41,
    "LUKE": 42, "LUK": 42, "LKE": 42, "JOHN": 43, "JHN": 43, "ACTS": 44, "ACT": 44,
    "ROM": 45, "1CO": 46, "2CO": 47, "GAL": 48, "EPH": 49, "PHP": 50,
    "COL": 51, "1TH": 52, "2TH": 53, "1TI": 54, "2TI": 55, "TIT": 56,
    "PHM": 57, "HEB": 58, "JAS": 59, "1PE": 60, "2PE": 61, "1JN": 62, "2JN": 63, "3JN": 64,
    "JUDE": 65, "JUD": 65, "REV": 66,
}

# (json id, display name, bible.com slug after /reading-plans/, total days)
YOUVERSION_CURATED_PLANS: list[tuple[str, str, str, int]] = [
    (
        "mcheyne-1year-youversion",
        "M'Cheyne One Year Reading Plan (YouVersion / Crossway)",
        "24-mcheyne-one-year-reading-plan",
        365,
    ),
    (
        "psalms-proverbs-youversion-372",
        "Psalms & Proverbs (YouVersion; ~2× Psalms & 12× Proverbs per year)",
        "15-psalms-and-proverbs",
        372,
    ),
    (
        "psalms-proverbs-youversion-31",
        "Psalms and Proverbs in 31 Days (YouVersion)",
        "104-psalms-and-proverbs-in-31-days",
        31,
    ),
    (
        "bible-in-a-year-youversion-abs",
        "The Bible in a Year (YouVersion; American Bible Society)",
        "158-the-bible-in-a-year",
        365,
    ),
    (
        "bible-in-a-year-youversion-ligonier",
        "Bible in a Year (YouVersion; Ligonier — OT + NT daily)",
        "1335-bible-in-a-year",
        365,
    ),
]

# Top 10 yearly plans from Bible Study Tools (fetchable)
BST_YEARLY_PLANS = [
    (1, "chronological-1year", "Chronological Bible (1 Year)", "chronological.html"),
    (2, "book-order-1year", "Book Order Bible (1 Year)", "book-order.html"),
    (3, "ot-and-nt-1year", "Old and New Testament (1 Year)", "old-testament-and-new-testament.html"),
    (4, "classic-1year", "Classic Bible (1 Year)", "classic.html"),
    (5, "one-year-immersion", "One-Year Immersion (OT 1×, NT 3×)", "one-year-immersion-plan.html"),
    (6, "stay-on-track", "Stay-on-Track Bible (1 Year)", "stay-on-track.html"),
    (7, "busy-life-1year", "The Busy-Life Bible (1 Year)", "busy-life-plan.html"),
]


def _parse_bst_days(html: str, max_day: int = 365) -> list[dict]:
    """Extract Day N / reading blocks from BST HTML."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = " ".join(text.split())
    entries = []
    for m in re.finditer(r"Day\s+(\d+)\s+(.+?)(?=Day\s+\d+\s+|\Z)", text, re.DOTALL):
        day = int(m.group(1))
        if day > max_day:
            break
        reading = m.group(2).strip()
        chapters = parse_day_text(reading)
        if chapters:
            entries.append({"day": day, "chapters": chapters})
    return entries


def chapters_from_bible_com_html(html: str) -> list[str]:
    """
    Extract passage list from a bible.com plan day page. Prefer /bible/<vid>/<ABBR>.<ch>.<CODE>
    links (stable on current YouVersion web).
    """
    pairs = re.findall(r"/bible/\d+/([A-Z0-9]+)\.(\d+)\.[A-Z]+", html, re.I)
    seen: set[tuple[str, str]] = set()
    out: list[str] = []
    for abbr, ch in pairs:
        au = abbr.upper()
        key = (au, ch)
        if key in seen:
            continue
        seen.add(key)
        bnum = BIBLE_COM_ABBR_TO_NUM.get(au)
        if not bnum:
            continue
        out.append(f"{bnum}:{ch}")
    if out:
        return out
    refs = re.findall(r"\[(Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|"
                      r"Judges|Ruth|1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|2 Chronicles|"
                      r"Ezra|Nehemiah|Esther|Job|Psalm|Psalms|Proverbs|Ecclesiastes|"
                      r"Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|"
                      r"Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|"
                      r"Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|"
                      r"Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|"
                      r"Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|"
                      r"Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|"
                      r"Jude|Revelation)\s+(\d+)\]", html, re.I)
    if refs:
        return parse_day_text("; ".join(f"{b} {c}" for b, c in refs))
    refs2 = re.findall(
        r"/(GEN|EXO|EXOD|LEV|NUM|DEUT|DEU|JOSH|JOS|JDG|RUTH|RUT|"
        r"1SAM|1SA|2SAM|2SA|1KGS|1KI|2KGS|2KI|1CHR|1CH|2CHR|2CH|"
        r"EZRA|EZR|NEH|ESTH|EST|JOB|PS|PSA|PROV|PRO|ECCL|ECC|SONG|SNG|"
        r"ISA|JER|LAM|EZK|DAN|HOS|JOEL|JOL|AMOS|AMO|OBA|JON|MIC|NAH|NAM|HAB|ZEP|HAG|ZEC|MAL|"
        r"MATT|MAT|MARK|MRK|LUKE|LUK|LKE|JOHN|JHN|ACTS|ACT|ROM|"
        r"1CO|2CO|GAL|EPH|PHP|COL|1TH|2TH|1TI|2TI|TIT|PHM|HEB|JAS|"
        r"1PE|2PE|1JN|2JN|3JN|JUDE|JUD|REV)\.(\d+)\.",
        html, re.I
    )
    return [f"{BIBLE_COM_ABBR_TO_NUM[a.upper()]}:{c}" for a, c in refs2
            if a.upper() in BIBLE_COM_ABBR_TO_NUM]


def fetch_bible_com_plan(plan_slug: str, plan_id: str, name: str, total_days: int) -> dict:
    """Fetch one YouVersion / bible.com plan by crawling each day page."""
    base_url = f"https://www.bible.com/reading-plans/{plan_slug}"
    entries: list[dict] = []
    for day in range(1, total_days + 1):
        url = f"{base_url}/day/{day}"
        html = None
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=45, headers=BIBLE_COM_HEADERS)
                r.raise_for_status()
                html = r.text
                break
            except requests.RequestException as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    print(f"\n  Day {day}: fetch failed ({e}), using empty")
                    entries.append({"day": day, "chapters": []})
                    break
        if html is None:
            continue
        chapters = chapters_from_bible_com_html(html)
        entries.append({"day": day, "chapters": chapters})
        print(f"  Day {day}/{total_days}: {len(chapters)} chapters", end="\r")
        time.sleep(0.12)
    print()
    return {
        "id": plan_id,
        "name": name,
        "days": total_days,
        "source": base_url,
        "entries": entries,
    }


def fetch_bst_plan(plan_id: str, name: str, slug: str) -> dict:
    """Fetch any BST yearly plan by slug."""
    url = f"https://www.biblestudytools.com/bible-reading-plan/{slug}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    entries = _parse_bst_days(r.text)
    return {
        "id": plan_id,
        "name": name,
        "days": 365,
        "source": url,
        "entries": entries,
    }


def fetch_bst_chronological_1yr() -> dict:
    """Fetch Chronological 1-year from Bible Study Tools."""
    url = "https://www.biblestudytools.com/bible-reading-plan/chronological.html"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    entries = _parse_bst_days(r.text)
    return {
        "id": "chronological-1year",
        "name": "Chronological Bible (1 Year)",
        "days": 365,
        "source": url,
        "entries": entries,
    }


def fetch_bst_ninety_day() -> dict:
    """Fetch Ninety-Day Challenge (sequential) from Bible Study Tools."""
    url = "https://www.biblestudytools.com/bible-reading-plan/ninety-day-challenge.html"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    entries = _parse_bst_days(r.text)
    return {
        "id": "ninety-day-challenge",
        "name": "Ninety-Day Challenge (Sequential)",
        "days": 90,
        "source": url,
        "entries": entries,
    }


def fetch_bible_com_chronological_90() -> dict:
    """Fetch Chronological in 90 Days from bible.com (YouVersion)."""
    return fetch_bible_com_plan(
        "40606-chronological-in-90-days",
        "chronological-90days",
        "Chronological in 90 Days",
        90,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Bible reading plans")
    parser.add_argument("--yearly", action="store_true", help="Fetch top 7 yearly plans from Bible Study Tools")
    parser.add_argument("--90day", action="store_true", dest="ninety_day", help="Fetch 90-day plans (BST + bible.com)")
    parser.add_argument(
        "--youversion",
        action="store_true",
        help="Fetch curated bible.com plans (M'Cheyne, Psalms & Proverbs, Bible in a Year, …)",
    )
    parser.add_argument("--all", action="store_true", help="Fetch everything (default)")
    args = parser.parse_args()
    if not (args.yearly or args.ninety_day or args.youversion or args.all):
        args.all = True

    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    if args.all or args.yearly:
        for rank, plan_id, name, slug in BST_YEARLY_PLANS:
            print(f"Fetching #{rank} {name}...")
            try:
                p = fetch_bst_plan(plan_id, name, slug)
                out = PLANS_DIR / f"{plan_id}.json"
                out.write_text(json.dumps(p, indent=2, ensure_ascii=False))
                print(f"  Saved {len(p['entries'])} days -> {out.name}")
            except Exception as e:
                print(f"  Failed: {e}")

    if args.all or args.ninety_day:
        print("Fetching Ninety-Day Challenge...")
        p2 = fetch_bst_ninety_day()
        out2 = PLANS_DIR / "ninety-day-challenge.json"
        out2.write_text(json.dumps(p2, indent=2, ensure_ascii=False))
        print(f"  Saved {len(p2['entries'])} days -> {out2.name}")

        print("Fetching Chronological in 90 Days (bible.com, 90 pages)...")
        p3 = fetch_bible_com_chronological_90()
        out3 = PLANS_DIR / "chronological-90days.json"
        out3.write_text(json.dumps(p3, indent=2, ensure_ascii=False))
        print(f"  Saved {len(p3['entries'])} days -> {out3.name}")

    if args.youversion:
        for json_id, title, slug, n_days in YOUVERSION_CURATED_PLANS:
            print(f"Fetching YouVersion: {title} ({n_days} days)...")
            try:
                p = fetch_bible_com_plan(slug, json_id, title, n_days)
                out = PLANS_DIR / f"{json_id}.json"
                out.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                nonempty = sum(1 for e in p["entries"] if e.get("chapters"))
                print(f"  Saved {len(p['entries'])} days ({nonempty} with passages) -> {out.name}")
            except Exception as e:
                print(f"  Failed: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
