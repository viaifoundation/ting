# Ting (聽) – Bible Reading Plan Audio Generator

Tools for generating Bible reading plan audio (MP3) from the Everest Audio Bible.  
Supports background music and volume adjustment (adapted from [devotion_tts](https://github.com/viaifoundation/devotion_tts)).

## Setup

```bash
# Clone and enter repo
git clone https://github.com/viaifoundation/ting.git && cd ting

# Create virtual environment
python -m venv venv

# Activate venv (do this before running any script)
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

Requires **ffmpeg** for pydub (mp3 support): `brew install ffmpeg` / `apt install ffmpeg`

**Running commands:** Activate the venv first (`source venv/bin/activate`), then run any script from the repo root. Example:
```bash
source venv/bin/activate
python scripts/firstlight.py
```

## Download chapter MP3s

Downloads Everest Audio Bible (Traditional Chinese, 48k), unzips, and arranges as one file per chapter:

```bash
python scripts/download_everest_audio.py
```

Options: `--dry-run`, `--start N`, `--end N`

## Concatenate + BGM + volume

Combine chapters into one daily MP3, with optional background music and volume controls:

```bash
# Concat only
python scripts/concat_daily.py -c "1:1,1:2,1:3" -o daily_001.mp3

# With background music (put BGM files in assets/bgm/)
python scripts/concat_daily.py -c "1:1,1:2" -o day.mp3 --bgm --bgm-volume -20 --speech-volume 2

# 2x speed (atempo, pitch preserved)
python scripts/concat_daily.py -c "1:1,1:2" -o day.mp3 --speed 2

# Recorded chapter voices (Everest = female, David Yen = male); per-source dB leveling before --speech-volume
python scripts/concat_daily.py -c "19:1,19:2" -o day.mp3 --chapter-voice male_then_female
# Choices: male | female | rotate | male_then_female | female_then_male | duplicate_random
# duplicate_random: optional --duplicate-random-seed N for reproducible order per chapter

# Mix BGM into an existing audio file
python scripts/mix_bgm.py -i daily_001.mp3 --bgm --bgm-track AmazingGrace.mp3
```

**Volume options:**
- `--bgm-volume` – BGM volume in dB (e.g. -20 = quieter, default -20)
- `--speech-volume` – Speech volume in dB (e.g. 2 = louder, 0 = no change)
- `--bgm-intro` – Music plays before speech (ms, default 4000)
- `--bgm-tail` – Music plays after speech (ms, default 3000)

## Reading plans

**Top 10 popular plans** (ranked), in `assets/bible/plans/`:

| # | Plan | Days | Description |
|---|------|------|-------------|
| 1 | `chronological-1year` | 365 | Events in historical order |
| 2 | `book-order-1year` | 365 | Genesis→Revelation, canon order |
| 3 | `ot-and-nt-1year` | 365 | OT + NT passage daily |
| 4 | `classic-1year` | 365 | 3 readings/day (M'Cheyne-style) |
| 5 | `one-year-immersion` | 365 | OT once, NT 3× |
| 6 | `stay-on-track` | 257 | Catch-up days built in |
| 7 | `busy-life-1year` | 365 | Lighter daily load |
| 8 | `chronological-90days` | 90 | Chronological in 90 days |
| 9 | `ninety-day-challenge` | 90 | Sequential Gen→Rev |
| 10 | `nt-40days` | 40 | NT in 40 days challenge |
| 11 | `nt-psalms-proverbs-90days` | 90 | NT, Psalms, & Proverbs in 90 days |

**Curated YouVersion (bible.com)** — popular / classic schedules, same JSON shape as other plans:

| JSON id | Days | Notes |
|---------|------|--------|
| `mcheyne-1year-youversion` | 365 | [M'Cheyne](https://www.bible.com/reading-plans/24-mcheyne-one-year-reading-plan) — four readings/day (Crossway) |
| `psalms-proverbs-youversion-372` | 372 | [Psalms & Proverbs](https://www.bible.com/reading-plans/15-psalms-and-proverbs) — ~2× Psalms & 12× Proverbs / year |
| `psalms-proverbs-youversion-31` | 31 | [Psalms + Proverbs in 31 days](https://www.bible.com/reading-plans/104-psalms-and-proverbs-in-31-days) |
| `bible-in-a-year-youversion-abs` | 365 | [Bible in a Year](https://www.bible.com/reading-plans/158-the-bible-in-a-year) (American Bible Society) |
| `bible-in-a-year-youversion-ligonier` | 365 | [Bible in a Year](https://www.bible.com/reading-plans/1335-bible-in-a-year) (Ligonier — OT + NT) |

**Refresh plans:**
```bash
python scripts/fetch_reading_plans.py --yearly     # Top 7 yearly from Bible Study Tools
python scripts/fetch_reading_plans.py --90day      # 90-day plans (BST + bible.com chronological)
python scripts/fetch_reading_plans.py --youversion # Curated YouVersion plans (slow: ~13 min, many HTTP requests)
python scripts/fetch_reading_plans.py --all        # BST yearly + 90-day only (not YouVersion curated)
```

**Validate plans** (chapter refs vs Protestant canon; wisdom-praise / psalms-30 / nt-pp90 invariants):

```bash
python scripts/validate_reading_plans.py
python scripts/validate_reading_plans.py --plan wisdom-praise-90days
```

`stay-on-track` warns about intentional catch-up gaps (not every calendar day has an entry).

**Generate daily MP3s** (Everest volume is low; use `--speech-volume 4`):
```bash
python scripts/generate_plan_audio.py chronological-1year -o audio/chronological-1year --speech-volume 4
python scripts/generate_plan_audio.py chronological-90days -o audio/chronological-90days --speech-volume 4
# Days 2–4 only
python scripts/generate_plan_audio.py chronological-1year -o audio/chronological-1year --start-day 2 --end-day 4 --speech-volume 4
# Custom start date (default: 2026-02-17)
python scripts/generate_plan_audio.py chronological-1year -o audio/chronological-1year --start-date 2026-02-17 --speech-volume 4
# 2x speed + BGM (add MP3/WAV files to assets/bgm/ first)
python scripts/generate_plan_audio.py chronological-90days -o audio/chronological-90days --speech-volume 4 --speed 2 --bgm
# Optionally add BGM only
python scripts/generate_plan_audio.py chronological-1year -o audio/chronological-1year --speech-volume 4 --bgm
```
Output: `YYYYMMDD_历史读经第N天.mp3` (plain) or `YYYYMMDD_90天历史读经第N天.mp3` (90-day). With `--bgm` and `--bgm-splits`, filenames use Chinese suffixes (原速上/中/下, 加速上/下, 倍速). Goes to `audio/` (gitignored).

Speed uses ffmpeg `atempo` (pitch preserved); `--speed 2` = 2x.

**Print plan content in Chinese:**
```bash
python scripts/print_plan_cn.py chronological-1year 4           # First 4 days
python scripts/print_plan_cn.py chronological-90days 4 2026-02-17   # With custom start date
```

**First light** – generate reading plan audio for a date range. Per day: prints plan content in [en] (ESV book names), [zh_cn], [zh_tw]; generates MP3 files per `--preset`. BGM split into smaller files for easier download. Uses Kiritimati (UTC+14) for "today" default.
```bash
python scripts/firstlight.py                                    # today, preset 1 (4 files)
python scripts/firstlight.py --start-date 2026-02-27 --num-days 5
python scripts/firstlight.py --start-date 2026-03-01 --end-date 2026-03-05
python scripts/firstlight.py --plan chronological-1year --plan-start-date 2026-01-01
python scripts/firstlight.py --preset 3                        # all 7 files
```
**Presets:** 1 (default)=4 files (1x plain+1.5x+2x BGM), 2=4 files (1x plain+BGM), 3=7 files (all).

Options: `--plan` (default chronological-90days), `--plan-start-date` (day 1), `--start-date`, `--end-date`, `--num-days` (if both `--end-date` and `--num-days` given, `--end-date` wins), `--preset`.

**Praise with Psalms** – generates a single 1.5× BGM file per day for the `psalms-30days` plan. Input is a day number or range (defaults to day 1). **Translation comparison is enabled by default** (CUV Everest + CUVC TTS), and filenames include `對照文理和合本` when comparison is on.
```bash
python scripts/praisewithpsalms.py              # Day 1 with comparison
python scripts/praisewithpsalms.py 1-7          # Days 1–7
python scripts/praisewithpsalms.py 8            # Day 8
python scripts/praisewithpsalms.py --no-compare # Without comparison
python scripts/praisewithpsalms.py 1-5 --trans cuvt,ncvs  # Different translations
```
Output filenames: `赞美诗篇第1天_詩1-5_對照文理和合本.mp3`

**Wisdom & Praise (Psalms + Proverbs)** – full Psalms (150) and Proverbs (31) split across **30, 45, 60, or 90 days** (`wisdom-praise-{30,45,60,90}days.json`). Regenerate JSON from the repo root:

```bash
python scripts/build_wisdom_praise_plans.py
```

**`wisdompraise.py`** – 1.5× + BGM per day; day number or range (no calendar dates). Default chapter voice is **male then female** per chapter (`--chapter-voice male_then_female`). Also: `female_then_male`, `duplicate_random` (+ optional `--duplicate-random-seed`), `rotate`, `male`, `female`.

```bash
python scripts/wisdompraise.py 1
python scripts/wisdompraise.py 1-5 --plan wisdom-praise-90days
python scripts/wisdompraise.py 1-30 --chapter-voice rotate
```

**`psprov.py`** (**ps** = Psalms, **prov** = Proverbs) — 30–372+ days with **`--voice-mode`** (`male_female` default, `female_male`, `duplicate_random`, `male`, `female`, `rotate`). Defaults to plan `wisdom-praise-90days`. List presets and plans: **`--list-presets`**. Older names `psalms_proverbs_audio.py` and `praise90.py` still forward here (stderr deprecation note).

**YouVersion Psalms & Proverbs** — `psprov.py` exposes **four** `--preset` values only (each pins a plan JSON + voice mode; overrides `--plan` / `--voice-mode`). Source schedules: [31-day](https://www.bible.com/reading-plans/104-psalms-and-proverbs-in-31-days), [372-day](https://www.bible.com/reading-plans/15-psalms-and-proverbs).

| `--preset` | Plan JSON | Days | Audio |
|------------|-----------|------|--------|
| `yv31-rotate` | `psalms-proverbs-youversion-31` | 31 | Rotate narrators by chapter (single pass) |
| `yv31-mf` | `psalms-proverbs-youversion-31` | 31 | Each chapter: male then female |
| `yv372-rotate` | `psalms-proverbs-youversion-372` | 372 | Rotate (single pass) |
| `yv372-mf` | `psalms-proverbs-youversion-372` | 372 | Each chapter: male then female |

Other reading plans (e.g. `wisdom-praise-90days`) are **not** presets: pass **`--plan`** and **`--voice-mode`** instead. **`firstlight.py --preset`** is unrelated (output bundle size: 1 / 2 / 3).

```bash
python scripts/psprov.py --list-presets
python scripts/psprov.py 1
python scripts/psprov.py 1-7 --voice-mode rotate
python scripts/psprov.py 1-5 --plan wisdom-praise-60days --voice-mode female_male
python scripts/psprov.py 1-31 --preset yv31-rotate
python scripts/psprov.py 1-372 --preset yv372-mf
```

Output filenames (wisdom-praise & YouVersion Psalms/Proverbs): descriptive `{N}天智慧讚美第{dd}天-{chapters}.mp3`. Double-voice: `{N}天智慧讚美對照第{dd}天-…`. Example day 1 of 90-day plan: `90天智慧讚美第01天-詩1-箴1.mp3` vs `90天智慧讚美對照第01天-詩1-箴1.mp3`. Details: `generate_plan_audio.py` module docstring; `psprov.py --list-presets`.

Plan files: `assets/bible/plans/wisdom-praise-{30,45,60,90}days.json`  
Shared options: `-o`, `--speech-volume` (default 4), `--use-tts`, `--interleave-tts`, `--compare`, `--trans`

**New Testament Challenges** – Dedicated scripts for focused New Testament study, following the `wisdompraise.py` method (single 1.5× BGM file per day). These scripts generate a consolidated daily audio file at high speed with background music.
- **NT in 40 Days**: `python scripts/nt40.py 1-40`
- **NT, Psalms, & Proverbs (90 Days)**: `python scripts/ntpp90.py 1-90`

Support for day ranges (e.g., `1-5`) and optional translation comparison:
```bash
python scripts/nt40.py 1           # Day 1 only
python scripts/nt40.py 1-5         # Days 1–5
python scripts/nt40.py 1 --compare # Enable translation comparison (CUV + CUVC)
```
Plan files: `assets/bible/plans/nt-40days.json`, `assets/bible/plans/nt-psalms-proverbs-90days.json`

**Daily cron** – run at 00:05 Kiritimati (e.g. 10:05 UTC) to generate today's MP3s (preset 1 = 4 files):
```bash
5 10 * * * cd /path/to/ting && source venv/bin/activate && python scripts/firstlight.py
```

## Layout

- `assets/bible/audio/chapters/` – one MP3 per chapter (gitignored)
- `assets/bible/audio/zips/` – downloaded ZIPs (gitignored)
- `assets/bible/plans/` – reading plan JSON files
- `assets/bgm/` – add your own BGM files (.mp3, .wav, .m4a). With `--bgm`, BGM rotates **per output file** by length: if the output is longer than one track, the next track is appended, and so on; when all tracks are used, the sequence loops. First track and rotation order are random for each file. Tracks are RMS-normalized for consistent volume.
- `audio/` – generated daily MP3s (gitignored)
- See `READING_PLAN_AUDIO_FEATURE_PLAN.md` for full feature plan

## Audio processing: what we tried

### Speed (2x playback)

| Approach | How | Result |
|----------|-----|--------|
| **asetrate + aresample** (ffmpeg) | Interpret 48k samples as 96k, resample back to 48k | ❌ **Not used** – doubles speed but raises pitch (chipmunk effect). User found tone wrong. |
| **atempo** (ffmpeg) | `atempo=2` time-stretches without pitch change | ✅ **Used** – 2x speed, natural pitch. Sounds good. |

Player 2x on the original 1x file also works (each player implements its own algorithm). We bake 2x with atempo for portability.

### BGM rotation

Rotation is **per output file**, not per day. If an output is longer than one music track, we append the next track (random order), and loop through all tracks when exhausted. The first track and sequence are randomized for each file. Tracks are RMS-normalized to -18 dBFS before `--bgm-volume` so different sources don't cause volume jumps.
