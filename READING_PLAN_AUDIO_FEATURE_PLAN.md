# Bible Reading Plan Audio – Feature Plan

This document outlines the feature to generate Bible reading plan audio (MP3) from the Everest Audio Bible, arrange chapter-level files, and produce one combined MP3 per day of a reading plan.

---

## 1. Source: Everest Audio Bible

- **URL**: https://www.everestaudiobible.org/mp3-download  
- **Content**: Traditional Chinese (有聲聖經) MP3, 48k.
- **Download pattern**: One ZIP per book (Genesis `01_GEN.zip` is available).
- **Base URL for zips**:  
  `https://www.everestaudiobible.org/mp3/website/Everest_Audio_Bible_48k/`  
- **Naming**: `NN_XXX.zip` (e.g. `02_EXO.zip`, `40_MAT.zip`, `66_REV.zip`).  
  Book numbers 1–66 match standard book IDs. `01` = Genesis, `02` = Exodus, … `66` = Revelation.

---

## 2. Local Layout: `assets/bible/audio/`

- **Path**: `assets/bible/audio/` (excluded from git via `.gitignore`).
- **Convention**: One MP3 per chapter so that any reading plan "day" can be built by concatenating a list of chapters.

```text
assets/bible/audio/
├── chapters/                    # One file per chapter (canonical source)
│   ├── 001_001.mp3             # Genesis 1
│   ├── … 066_022.mp3           # Revelation 22
├── zips/                       # Downloaded ZIPs
└── daily/                      # Generated: one MP3 per plan day
```

---

## 3. Download Script (Python)

Run `python scripts/download_everest_audio.py` to download all 66 books and arrange chapters.

---

## 4. Combining MP3s (One Day's Reading)

Use ffmpeg concat:  
`ffmpeg -f concat -safe 0 -i list.txt -c copy day_N.mp3`

**Speed:** `concat_daily.py` uses ffmpeg `atempo` for pitch-preserving speed (e.g. 2x).  
**BGM output:** With `--bgm`, filenames get `-bgm` suffix so both versions coexist.

---

## 5. Reading Plan DB Schema

```sql
CREATE TABLE reading_plan (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slug VARCHAR(64) NOT NULL UNIQUE,
  name_en VARCHAR(255) NOT NULL,
  total_days INT UNSIGNED NOT NULL,
  ...
);

CREATE TABLE reading_plan_day (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  plan_id INT UNSIGNED NOT NULL,
  day_index INT UNSIGNED NOT NULL,
  segment_order TINYINT UNSIGNED NOT NULL DEFAULT 1,
  book TINYINT UNSIGNED NOT NULL,
  chapter SMALLINT UNSIGNED NOT NULL,
  ...
);
```

---

## 6. References

- **Everest MP3 download**: https://www.everestaudiobible.org/mp3-download  
- **Repo**: https://github.com/viaifoundation/ting
