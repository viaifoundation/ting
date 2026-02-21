# Ting – Bible Reading Plan Audio Generator

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
python scripts/first_light.py
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
# 2x speed + BGM (add MP3/WAV files to assets/bgm/ first)
python scripts/generate_plan_audio.py chronological-90days -o output/chronological-90days --speech-volume 4 --speed 2 --bgm
# Optionally add BGM only
python scripts/generate_plan_audio.py chronological-1year -o output/chronological-1year --speech-volume 4 --bgm
```
Output: `YYYYMMDD_历史读经第N天.mp3` (historical 1-year) or `YYYYMMDD_90天历史读经第N天.mp3` (90-day). With `--bgm`, filenames get `-bgm` suffix (e.g. `YYYYMMDD_历史读经第1天-bgm.mp3`) so both versions coexist. Goes to `output/` (gitignored).

Speed uses ffmpeg `atempo` (pitch preserved); `--speed 2` = 2x.

**Print plan content in Chinese:**
```bash
python scripts/print_plan_cn.py chronological-1year 4           # First 4 days
python scripts/print_plan_cn.py chronological-90days 4 2026-02-17   # With custom start date
```

**First light** – generate today's 90-day chronological reading (one day, both with and without BGM). Uses Kiritimati (Christmas Island) timezone (UTC+14), the first to see each new day:
```bash
python scripts/first_light.py
python scripts/first_light.py --start-date 2026-02-17
```

## Layout

- `assets/bible/audio/chapters/` – one MP3 per chapter (gitignored)
- `assets/bible/audio/zips/` – downloaded ZIPs (gitignored)
- `assets/bible/plans/` – reading plan JSON files
- `assets/bgm/` – add your own BGM files (.mp3, .wav, .m4a). With `--bgm`, BGM rotates **per output file** by length: if the output is longer than one track, the next track is appended, and so on; when all tracks are used, the sequence loops. First track and rotation order are random for each file. Tracks are RMS-normalized for consistent volume.
- `output/` – generated daily MP3s (gitignored)
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
