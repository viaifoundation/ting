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


# Short abbreviations used for generating filenames (book_num -> prefix)
BOOK_FILENAME_ABBR: dict[int, str] = {
    1: "gen", 2: "exo", 3: "lev", 4: "num", 5: "deu",
    6: "jos", 7: "jdg", 8: "rut", 9: "1sa", 10: "2sa",
    11: "1ki", 12: "2ki", 13: "1ch", 14: "2ch", 15: "ezr",
    16: "neh", 17: "est", 18: "job", 19: "ps", 20: "prov",
    21: "ecc", 22: "sng", 23: "isa", 24: "jer", 25: "lam",
    26: "eze", 27: "dan", 28: "hos", 29: "joe", 30: "amo",
    31: "oba", 32: "jon", 33: "mic", 34: "nah", 35: "hab",
    36: "zep", 37: "hag", 38: "zec", 39: "mal",
    40: "mat", 41: "mar", 42: "luk", 43: "joh", 44: "act",
    45: "rom", 46: "1co", 47: "2co", 48: "gal", 49: "eph",
    50: "php", 51: "col", 52: "1th", 53: "2th", 54: "1ti",
    55: "2ti", 56: "tit", 57: "phm", 58: "heb", 59: "jas",
    60: "1pe", 61: "2pe", 62: "1jn", 63: "2jn", 64: "3jn",
    65: "jud", 66: "rev",
}

# Traditional Chinese short-form abbreviations for filenames (book_num -> 縮寫)
BOOK_FILENAME_ABBR_ZH_TW: dict[int, str] = {
    1: "創", 2: "出", 3: "利", 4: "民", 5: "申",
    6: "書", 7: "士", 8: "得", 9: "撒上", 10: "撒下",
    11: "王上", 12: "王下", 13: "代上", 14: "代下", 15: "拉",
    16: "尼", 17: "斯", 18: "伯", 19: "詩", 20: "箴",
    21: "傳", 22: "歌", 23: "賽", 24: "耶", 25: "哀",
    26: "結", 27: "但", 28: "何", 29: "珥", 30: "摩",
    31: "俄", 32: "拿", 33: "彌", 34: "鴻", 35: "哈",
    36: "番", 37: "該", 38: "亞", 39: "瑪",
    40: "太", 41: "可", 42: "路", 43: "約", 44: "徒",
    45: "羅", 46: "林前", 47: "林後", 48: "加", 49: "弗",
    50: "腓", 51: "西", 52: "帖前", 53: "帖後", 54: "提前",
    55: "提後", 56: "多", 57: "門", 58: "來", 59: "雅",
    60: "彼前", 61: "彼後", 62: "約一", 63: "約二", 64: "約三",
    65: "猶", 66: "啟",
}


def chapters_to_filename(
    chapters: list[str],
    abbr: dict[int, str] | None = None,
) -> str:
    """
    Convert a list of 'book:chapter' strings into a compact filename-safe string.

    Groups consecutive chapters per book and collapses them into ranges.

    Args:
        chapters: list of 'book:chapter' strings, e.g. ['19:1','19:5','20:1']
        abbr:     book-number -> abbreviation mapping.
                  Defaults to BOOK_FILENAME_ABBR (English, e.g. 'ps', 'prov').
                  Pass BOOK_FILENAME_ABBR_ZH_TW for Traditional Chinese (e.g. '詩', '箴').

    Example (English):  ['19:1'...'19:5','20:1'] -> 'ps1-5_prov1'
    Example (zh_tw):    ['19:1'...'19:5','20:1'] -> '詩1-5_箴1'
    """
    if abbr is None:
        abbr = BOOK_FILENAME_ABBR
    if not chapters:
        return "nodata"
    parts = []
    i = 0
    while i < len(chapters):
        book_num = int(chapters[i].split(":")[0])
        ch_num = int(chapters[i].split(":")[1])
        ch_nums = [ch_num]
        j = i + 1
        while j < len(chapters):
            b, c = chapters[j].split(":")
            if int(b) == book_num and int(c) == ch_nums[-1] + 1:
                ch_nums.append(int(c))
                j += 1
            else:
                break
        i = j
        book_abbr = abbr.get(book_num, f"b{book_num}")
        if len(ch_nums) == 1:
            parts.append(f"{book_abbr}{ch_nums[0]}")
        else:
            parts.append(f"{book_abbr}{ch_nums[0]}-{ch_nums[-1]}")
    return "_".join(parts)


def load_plan(path: Path) -> dict:
    """Load plan JSON. Returns {id, name, days, source, entries: [[chapters]]}."""
    import json
    return json.loads(path.read_text())


def save_plan(plan: dict, path: Path) -> None:
    """Save plan JSON."""
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
