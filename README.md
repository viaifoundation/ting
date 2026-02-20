# Ting – Bible Reading Plan Audio

Tools for generating Bible reading plan audio (MP3) from the Everest Audio Bible.  
Supports background music and volume adjustment (adapted from [devotion_tts](https://github.com/viaifoundation/devotion_tts)).

## Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Requires **ffmpeg** for pydub (mp3 support): `brew install ffmpeg` / `apt install ffmpeg`

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

# Mix BGM into an existing audio file
python scripts/mix_bgm.py -i daily_001.mp3 --bgm --bgm-track AmazingGrace.mp3
```

**Volume options:**
- `--bgm-volume` – BGM volume in dB (e.g. -20 = quieter, default -20)
- `--speech-volume` – Speech volume in dB (e.g. 2 = louder, 0 = no change)
- `--bgm-intro` – Music plays before speech (ms, default 4000)
- `--bgm-tail` – Music plays after speech (ms, default 3000)

## Reading plans

**Top 10 popular plans** (ranked), in `asset/bible/plans/`:

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

**Refresh plans:**
```bash
python scripts/fetch_reading_plans.py --yearly   # Top 7 yearly from Bible Study Tools
python scripts/fetch_reading_plans.py --90day    # 90-day plans
python scripts/fetch_reading_plans.py --all      # Everything
```

**Generate daily MP3s** (Everest volume is low; use `--speech-volume 4`):
```bash
python scripts/generate_plan_audio.py chronological-1year -o output/chronological-1year --speech-volume 4
python scripts/generate_plan_audio.py chronological-90days -o output/chronological-90days --speech-volume 4
# Days 2–4 only
python scripts/generate_plan_audio.py chronological-1year -o output/chronological-1year --start-day 2 --end-day 4 --speech-volume 4
# Custom start date (default: 2026-02-17)
python scripts/generate_plan_audio.py chronological-1year -o output/chronological-1year --start-date 2026-02-17 --speech-volume 4
# Optionally add BGM
python scripts/generate_plan_audio.py chronological-1year -o output/chronological-1year --speech-volume 4 --bgm
```
Output: `YYYYMMDD_历史读经第N天.mp3` (historical 1-year) or `YYYYMMDD_90天历史读经第N天.mp3` (90-day). Goes to `output/` (gitignored).

**Print plan content in Chinese:**
```bash
python scripts/print_plan_cn.py chronological-1year 4           # First 4 days
python scripts/print_plan_cn.py chronological-90days 4 2026-02-17   # With custom start date
```

## Layout

- `asset/bible/audio/chapters/` – one MP3 per chapter (gitignored)
- `asset/bible/audio/zips/` – downloaded ZIPs (gitignored)
- `asset/bible/plans/` – reading plan JSON files
- `output/` – generated daily MP3s (gitignored)
- `assets/bgm/` – add your own BGM files (.mp3, .wav, .m4a)
- See `READING_PLAN_AUDIO_FEATURE_PLAN.md` for full feature plan
