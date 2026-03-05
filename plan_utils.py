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
# English (ESV / standard), index 1-66
BOOK_ENGLISH = (
    "", "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges",
    "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
    "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John",
    "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians",
    "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus",
    "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John",
    "3 John", "Jude", "Revelation",
)
# Traditional Chinese (zh_TW), index 1-66
BOOK_CHINESE_TW = (
    "", "創世記", "出埃及記", "利未記", "民數記", "申命記", "約書亞記", "士師記",
    "路得記", "撒母耳記上", "撒母耳記下", "列王紀上", "列王紀下", "歷代志上", "歷代志下",
    "以斯拉記", "尼希米記", "以斯帖記", "約伯記", "詩篇", "箴言", "傳道書", "雅歌",
    "以賽亞書", "耶利米書", "耶利米哀歌", "以西結書", "但以理書", "何西阿書", "約珥書",
    "阿摩司書", "俄巴底亞書", "約拿書", "彌迦書", "那鴻書", "哈巴谷書", "西番雅書",
    "哈該書", "撒迦利亞書", "瑪拉基書", "馬太福音", "馬可福音", "路加福音", "約翰福音",
    "使徒行傳", "羅馬書", "哥林多前書", "哥林多後書", "加拉太書", "以弗所書", "腓立比書",
    "歌羅西書", "帖撒羅尼迦前書", "帖撒羅尼迦後書", "提摩太前書", "提摩太後書", "提多書",
    "腓利門書", "希伯來書", "雅各書", "彼得前書", "彼得後書", "約翰一書", "約翰二書",
    "約翰三書", "猶大書", "啟示錄",
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

# Add more short forms (Bible Study Tools, bible.com, bibleengine variants)
BOOK_INDEX.update({
    "1 Sam": 9, "2 Sam": 10, "2Sam": 10, "1 Kin": 11, "2 Kin": 12,
    "1 Chr": 13, "2 Chr": 14, "1 Cor": 46, "2 Cor": 47,
    "1 Thess": 52, "2 Thess": 53, "1 Tim": 54, "2 Tim": 55,
    "1 Pet": 60, "2 Pet": 61, "1 John": 62, "2 John": 63, "3 John": 64,
    "Song of Sol": 22, "Phil": 50, "Phlm": 57,
    "1Chr": 13, "1Ch": 13, "1Cor": 46, "1Co": 46, "1Jn": 62, "1Jo": 62,
    "1Kgs": 11, "1Ki": 11, "1K": 11, "1Pet": 60, "1Pe": 60, "1P": 60,
    "1Sam": 9, "1Sa": 9, "1S": 9, "1Thess": 52, "1Th": 52, "1Tim": 54, "1Ti": 54, "1Tm": 54,
    "2Chr": 14, "2Ch": 14, "2Cor": 47, "2Co": 47, "2Jn": 63, "2Jo": 63,
    "2Kgs": 12, "2Ki": 12, "2K": 12, "2Pet": 61, "2Pe": 61, "2P": 61,
    "2Sam": 10, "2Sa": 10, "2S": 10, "2Thess": 53, "2Th": 53, "2Tim": 55, "2Ti": 55, "2Tm": 55,
    "3Jn": 64, "3Jo": 64, "3J": 64,
    "Ac": 44, "Act": 44, "Acts": 44, "Am": 30, "Amo": 30, "Amos": 30,
    "Col": 51, "Cs": 51, "Da": 27, "Dn": 27, "Dan": 27, "Daniel": 27,
    "De": 5, "Deu": 5, "Deut": 5, "Dt": 5, "Ec": 21, "Ecc": 21, "Eccl": 21,
    "Ep": 49, "Eph": 49, "Es": 17, "Est": 17, "Esth": 17, "Esther": 17,
    "Ex": 2, "Exo": 2, "Exod": 2, "Exodus": 2, "Eze": 26, "Ezek": 26, "Ezekiel": 26,
    "Ezr": 15, "Ezra": 15, "Ga": 48, "Gal": 48, "Ge": 1, "Gen": 1, "Gn": 1, "Genesis": 1,
    "Hab": 35, "Habakkuk": 35, "Hag": 37, "Hg": 37, "Haggai": 37,
    "Hb": 58, "Heb": 58, "Hebrews": 58, "Ho": 28, "Hos": 28, "Hs": 28, "Hosea": 28,
    "Is": 23, "Isa": 23, "Isaiah": 23, "Jam": 59, "Jas": 59, "James": 59,
    "Jb": 18, "Jd": 65, "Jdg": 7, "Jg": 7, "Jer": 24, "Jr": 24, "Jeremiah": 24,
    "Jl": 29, "Jm": 59, "Job": 18, "Joe": 29, "Joel": 29, "Joh": 43, "John": 43, "Jn": 43,
    "Jnh": 32, "Jon": 32, "Jonah": 32, "Jos": 6, "Josh": 6, "Joshua": 6,
    "Jud": 65, "Jude": 65, "Judg": 7, "Judges": 7,
    "La": 25, "Lam": 25, "Lm": 25, "Lamentations": 25,
    "Le": 3, "Lev": 3, "Lv": 3, "Leviticus": 3,
    "Lk": 42, "Lu": 42, "Luk": 42, "Luke": 42,
    "Mal": 39, "Malachi": 39, "Mar": 41, "Mark": 41, "Mat": 40, "Matt": 40, "Matthew": 40,
    "Mi": 33, "Mic": 33, "Micah": 33, "Mk": 41, "Mr": 41, "Mt": 40,
    "Na": 34, "Nah": 34, "Nahum": 34, "Ne": 16, "Neh": 16, "Nehemiah": 16,
    "Nm": 4, "No": 4, "Nu": 4, "Num": 4, "Numbers": 4,
    "Ob": 31, "Oba": 31, "Obad": 31, "Obadiah": 31,
    "Phi": 50, "Phil": 50, "Php": 50, "Pp": 50, "Philippians": 50,
    "Philem": 57, "Phlm": 57, "Phm": 57, "Pm": 57, "Philemon": 57,
    "Pr": 20, "Pro": 20, "Prov": 20, "Proverbs": 20,
    "Ps": 19, "Psa": 19, "Psalm": 19, "Psalms": 19,
    "Re": 66, "Rev": 66, "Rv": 66, "Revelation": 66,
    "Ro": 45, "Rom": 45, "Rm": 45, "Romans": 45,
    "Rt": 8, "Ru": 8, "Rut": 8, "Ruth": 8,
    "Sg": 22, "So": 22, "Son": 22, "Song": 22, "SS": 22,
    "Tit": 56, "Tt": 56, "Titus": 56,
    "Zc": 38, "Zec": 38, "Zech": 38, "Zechariah": 38,
    "Zep": 36, "Zeph": 36, "Zp": 36, "Zephaniah": 36,
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


def _chapters_to_str(
    chapters: list[str], book_names: tuple, sep: str, joiner: str, space_before_ch: bool = False
) -> str:
    """Convert ['1:1','1:2','1:3'] to formatted string."""
    if not chapters:
        return ""
    sp = " " if space_before_ch else ""
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
        name = book_names[book_num] if book_num < len(book_names) else str(book_num)
        if len(ch_nums) == 1:
            parts.append(f"{name}{sp}{ch_nums[0]}")
        elif ch_nums == list(range(ch_nums[0], ch_nums[-1] + 1)):
            parts.append(f"{name}{sp}{ch_nums[0]}-{ch_nums[-1]}")
        else:
            parts.append(f"{name}{sp}" + joiner.join(str(c) for c in ch_nums))
    return sep.join(parts)


def chapters_to_chinese(chapters: list[str], book_names: tuple = BOOK_CHINESE) -> str:
    """Convert ['1:1','1:2','1:3'] -> '创世记1-3' (or Traditional with book_names=BOOK_CHINESE_TW)."""
    return _chapters_to_str(chapters, book_names, "；", "、", space_before_ch=False)


def chapters_to_english(chapters: list[str]) -> str:
    """Convert ['1:1','1:2','1:3'] -> 'Genesis 1-3' (ESV book names)."""
    return _chapters_to_str(chapters, BOOK_ENGLISH, "; ", ", ", space_before_ch=True)


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
