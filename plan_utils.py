#!/usr/bin/env python3
"""
Utilities for parsing Bible reading plans.
Maps book names to 1-66 (Genesis=1 ... Revelation=66).
Outputs chapter lists as "book:chapter" for concat_daily.py.
"""

import re

# Chinese book names (Simplified), index 1-66
BOOK_CHINESE = (
    "", "创世记", "出埃及记", "利未记", "民数记", "申命记", "约书亚记", "士师记",
    "路得记", "撒母耳记上", "撒母耳记下", "列王纪上", "列王纪下", "历代志上", "历代志下",
    "以斯拉记", "尼希米记", "以斯帖记", "约伯记", "诗篇", "箴言", "传道书", "雅歌",
    "以赛亚书", "耶利米书", "耶利米哀歌", "以西结书", "但以理书", "何西阿书", "约珥书",
    "阿摩司书", "俄巴底亚书", "约拿书", "弥迦书", "那鸿书", "哈巴谷书", "西番雅书",
    "哈该书", "撒迦利亚书", "玛拉基书", "马太福音", "马可福音", "路加福音", "约翰福音",
    "使徒行传", "罗马书", "哥林多前书", "哥林多后书", "加拉太书", "以弗所书", "腓立比书",
    "歌罗西书", "帖撒罗尼迦前书", "帖撒罗尼迦后书", "提摩太前书", "提摩太后书", "提多书",
    "腓利门书", "希伯来书", "雅各书", "彼得前书", "彼得后书", "约翰一书", "约翰二书",
    "约翰三书", "犹大书", "启示录",
)
from pathlib import Path

# Book name → number (1-66). Long names first for matching.
BOOK_INDEX = {
    "1 Chronicles": 13, "1 Corinthian": 46, "1 Corinthians": 46,
    "1 John": 62, "1 Kings": 11, "1 Peter": 60, "1 Samuel": 9,
    "1 Thessalonians": 52, "1 Timothy": 54,
    "2 Chronicles": 14, "2 Corinthians": 47, "2 John": 63,
    "2 Kings": 12, "2 Peter": 61, "2 Samuel": 10, "2 Thessalonians": 53,
    "2 Timothy": 55, "3 John": 64,
    "Acts": 44, "Amos": 30,
    "Colossians": 51,
    "Daniel": 27, "Deuteronomy": 5,
    "Ecclesiastes": 21, "Ephesians": 49, "Esther": 17, "Exodus": 2,
    "Ezekiel": 26, "Ezra": 15,
    "Galatians": 48, "Genesis": 1,
    "Habakkuk": 35, "Haggai": 37, "Hebrews": 58, "Hosea": 28,
    "Isaiah": 23,
    "James": 59, "Jeremiah": 24, "Job": 18, "Joel": 29, "John": 43,
    "Jonah": 32, "Joshua": 6, "Jude": 65, "Judges": 7,
    "Lamentations": 25, "Leviticus": 3, "Luke": 42,
    "Malachi": 39, "Mark": 41, "Matthew": 40, "Micah": 33,
    "Nahum": 34, "Nehemiah": 16, "Numbers": 4,
    "Obadiah": 31,
    "Philippians": 50, "Philemon": 57, "Proverbs": 20,
    "Psalm": 19, "Psalms": 19,
    "Revelation": 66, "Romans": 45, "Ruth": 8,
    "Song of Solomon": 22, "Song of Songs": 22,
}

# Add more short forms (Bible Study Tools, bible.com use these)
BOOK_INDEX.update({
    "1 Sam": 9, "2 Sam": 10, "2Sam": 10, "1 Kin": 11, "2 Kin": 12,
    "1 Chr": 13, "2 Chr": 14, "1 Cor": 46, "2 Cor": 47,
    "1 Thess": 52, "2 Thess": 53, "1 Tim": 54, "2 Tim": 55,
    "1 Pet": 60, "2 Pet": 61, "1 John": 62, "2 John": 63, "3 John": 64,
    "Song of Sol": 22, "Phil": 50, "Phlm": 57,
    "1Chr": 13, "1Cor": 46, "1Jn": 62, "1Kgs": 11, "1Pet": 60,
    "1Sam": 9, "1Thess": 52, "1Tim": 54,
    "2Chr": 14, "2Cor": 47, "2Jn": 63, "2Kgs": 12, "2Pet": 61,
    "2Sam": 10, "2Thess": 53, "2Tim": 55, "3Jn": 64,
    "Acts": 44, "Amos": 30, "Col": 51, "Dan": 27, "Deut": 5,
    "Eccl": 21, "Eph": 49, "Esth": 17, "Exod": 2, "Ezek": 26,
    "Ezra": 15, "Gal": 48, "Gen": 1, "Hab": 35, "Hag": 37,
    "Heb": 58, "Hos": 28, "Isa": 23, "Jas": 59, "Jer": 24,
    "Job": 18, "Joel": 29, "John": 43, "Jonah": 32, "Josh": 6,
    "Jude": 65, "Judg": 7, "Lam": 25, "Lev": 3, "Luke": 42,
    "Mal": 39, "Mark": 41, "Matt": 40, "Mic": 33, "Nah": 34,
    "Neh": 16, "Num": 4, "Obad": 31, "Phil": 50, "Phlm": 57,
    "Prov": 20, "Ps": 19, "Rev": 66, "Rom": 45, "Ruth": 8,
    "Song": 22, "Zech": 38, "Zeph": 36,
})

# Sort by length descending for longest-match
_SORTED_NAMES = sorted(BOOK_INDEX.keys(), key=len, reverse=True)


def _find_book(s: str) -> tuple[int | None, str]:
    """Find first book name in s. Return (book_num, remainder)."""
    s = s.strip()
    for name in _SORTED_NAMES:
        if s.startswith(name) or s.lower().startswith(name.lower()):
            rest = s[len(name):].strip()
            return BOOK_INDEX[name], rest
    return None, s


def parse_ref(text: str) -> list[tuple[int, int]]:
    """
    Parse a single reference like "Genesis 1-3" or "Psalm 119:1-88".
    Returns list of (book, chapter) pairs. Verse refs round to full chapter.
    """
    result = []
    # Split by ; or , for multiple refs
    parts = re.split(r"[,;]| and ", text, flags=re.I)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        book, rest = _find_book(part)
        if book is None:
            continue
        # rest might be: "1-3", "1", "119:1-88", "5:1-10", empty (whole book)
        rest = rest.strip()
        if not rest:
            # Whole book - assume chapter 1 for single-chapter books
            result.append((book, 1))
            continue
        # Match chapter or chapter:verse
        m = re.match(r"(\d+)(?:\s*[-–]\s*(\d+))?(?::\d+(?:-\d+)?)?", rest)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            for ch in range(start, end + 1):
                result.append((book, ch))
    return result


def parse_day_text(text: str) -> list[str]:
    """
    Parse a day's reading text (e.g. "Genesis 1-3; Exodus 4-6").
    Returns list of "book:chapter" strings.
    """
    seen = set()
    out = []
    # Split by semicolon or ";" for multiple refs; some use ";" others ","
    # Also handle "Genesis 1–3" (en-dash)
    text = text.replace("–", "-").replace("—", "-")
    # Split on semicolons first; each segment may have "Book X-Y"
    for block in re.split(r"\s*;\s*", text):
        block = block.strip()
        if not block:
            continue
        for ref in parse_ref(block):
            key = ref
            if key not in seen:
                seen.add(key)
                out.append(f"{ref[0]}:{ref[1]}")
    return out


def load_plan(path: Path) -> dict:
    """Load plan JSON. Returns {id, name, days, source, entries: [[chapters]]}."""
    import json
    return json.loads(path.read_text())


def save_plan(plan: dict, path: Path) -> None:
    """Save plan JSON."""
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
