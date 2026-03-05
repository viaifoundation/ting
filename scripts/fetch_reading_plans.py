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
    base = "https://www.bible.com/reading-plans/40606-chronological-in-90-days/day"
    entries = []
    for day in range(1, 91):
        url = f"{base}/{day}"
        html = None
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=30)
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
        # Extract scripture links: [Genesis 1](url) pattern
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
            chapters = parse_day_text("; ".join(f"{b} {c}" for b, c in refs))
        else:
            # Fallback: look for GEN.1 style in hrefs (YouVersion + bibleengine variants)
            # YouVersion: gen,exo,lev,num,deu,jos,jdg,rut,1sa,2sa,1ki,2ki,1ch,2ch,ezr,neh,est,job,psa,pro,ecc,sng,isa,jer,lam,ezk,dan,hos,jol,amo,oba,jon,mic,nam,hab,zep,hag,zec,mal,mat,mrk,lke,jhn,act,rom,1co,2co,gal,eph,php,col,1th,2th,1ti,2ti,tit,phm,heb,jas,1pe,2pe,1jn,2jn,3jn,jud,rev
            # Note: YouVersion uses LKE for Luke, NAM for Nahum
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
            abbr_to_num = {
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
            chapters = [f"{abbr_to_num.get(a.upper(), 0)}:{c}" for a, c in refs2
                       if a.upper() in abbr_to_num]
        entries.append({"day": day, "chapters": chapters})
        print(f"  Day {day}: {len(chapters)} chapters", end="\r")
    print()
    return {
        "id": "chronological-90days",
        "name": "Chronological in 90 Days",
        "days": 90,
        "source": "https://www.bible.com/reading-plans/40606-chronological-in-90-days",
        "entries": entries,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Bible reading plans")
    parser.add_argument("--yearly", action="store_true", help="Fetch top 7 yearly plans from Bible Study Tools")
    parser.add_argument("--90day", action="store_true", dest="ninety_day", help="Fetch 90-day plans (BST + bible.com)")
    parser.add_argument("--all", action="store_true", help="Fetch everything (default)")
    args = parser.parse_args()
    if not (args.yearly or args.ninety_day or args.all):
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

    print("Done.")


if __name__ == "__main__":
    main()
