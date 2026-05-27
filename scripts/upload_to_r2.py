#!/usr/bin/env python3
"""
Upload generated Bible MP3 and MP4 files to Cloudflare R2.
Falls back to Wrangler CLI if boto3 is not installed.

Requires:
  - CLOUDFLARE_ACCOUNT_ID (in environment or ~/.secrets)
  - For boto3: R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY
  - For wrangler: Active authentication (CLOUDFLARE_API_TOKEN with R2 permissions or wrangler login)
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Default bucket name
DEFAULT_BUCKET = "shema-media"

def upload_via_boto3(account_id: str, access_key: str, secret_key: str, bucket_name: str, local_path: Path, r2_key: str, download_name: str = None) -> bool:
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        return False

    try:
        s3 = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(signature_version="s3v4")
        )
        
        # Check if file already exists in R2
        try:
            s3.head_object(Bucket=bucket_name, Key=r2_key)
            print(f"  ⏭️  Already exists in R2: {r2_key}")
            return True
        except:
            # File doesn't exist, proceed with upload
            pass

        extra_args = {}
        if download_name:
            import urllib.parse
            encoded_name = urllib.parse.quote(download_name)
            extra_args["ContentDisposition"] = f"attachment; filename*=UTF-8''{encoded_name}"

        print(f"  📤 Uploading (boto3): {local_path.name} -> {r2_key} ...")
        s3.upload_file(
            Filename=str(local_path),
            Bucket=bucket_name,
            Key=r2_key,
            ExtraArgs=extra_args if extra_args else None
        )
        print("    ✅ Upload completed!")
        return True
    except Exception as e:
        print(f"  ❌ Boto3 upload failed: {e}")
        return False


def upload_via_wrangler(bucket_name: str, local_path: Path, r2_key: str) -> bool:
    print(f"  📤 Uploading (wrangler): {local_path.name} -> {r2_key} ...")
    cmd = [
        "npx", "wrangler", "r2", "object", "put",
        f"{bucket_name}/{r2_key}",
        "--file", str(local_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("    ✅ Upload completed!")
            return True
        else:
            print(f"  ❌ Wrangler failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ❌ Error calling wrangler: {e}")
        return False


def get_chinese_filename(filename: str) -> str | None:
    import re
    import json
    from pathlib import Path
    
    # Match: {plan_id}-day{day}-{rest}.{ext}
    match = re.match(r"^([\w-]+)-day(\d+)-(.*?)\.(mp3|mp4)$", filename)
    if not match:
        return None
        
    plan_id = match.group(1)
    day = int(match.group(2))
    ext = match.group(4)
    
    repo_root = Path(__file__).resolve().parent.parent
    plan_path = repo_root / "assets" / "bible" / "plans" / f"{plan_id}.json"
    if not plan_path.exists():
        return None
        
    try:
        plan = json.loads(plan_path.read_text())
        entries = plan.get("entries", [])
        entry = next((e for e in entries if e["day"] == day), None)
        if not entry or not entry.get("chapters"):
            return None
            
        chapters = entry["chapters"]
        plan_days = plan["days"]
        
        # Add repo root to path for importing plan_utils and generate_plan_audio
        import sys
        sys.path.insert(0, str(repo_root))
        sys.path.insert(0, str(repo_root / "scripts"))
        from plan_utils import BOOK_FILENAME_ABBR_ZH_TW, chapters_to_filename
        from generate_plan_audio import (
            wisdom_praise_filename_label,
            chrono_filename_label,
            WISDOM_PRAISE_STYLE_PLANS,
            CHRONO_STYLE_PLANS,
            PLAN_FILENAME_ZH_TW
        )
        
        # Determine if it uses compare voice (contains _compare or -compare or 对照)
        is_compare = "compare" in filename or "對照" in filename or "对照" in filename
        chapter_voice = "male_then_female" if is_compare else "rotate"
        
        _ch_join = "-"
        
        if plan_id in WISDOM_PRAISE_STYLE_PLANS:
            label = wisdom_praise_filename_label(plan_days, day, chapter_voice, lang="zh-tw")
            ch_str = chapters_to_filename(chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups=_ch_join)
            zh_base = f"{label}-{ch_str}"
        elif plan_id in CHRONO_STYLE_PLANS:
            label = chrono_filename_label(plan_id, day, chapter_voice, lang="zh-tw")
            ch_str = chapters_to_filename(chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups=_ch_join)
            zh_base = f"{label}-{ch_str}"
        else:
            name_fmt = PLAN_FILENAME_ZH_TW.get(plan_id, "聆聽第{i}天")
            ch_str = chapters_to_filename(chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups=_ch_join)
            zh_base = f"{name_fmt.format(i=day)}-{ch_str}"
            
        # Determine suffix from the rest of the filename
        suffix = ""
        # Look for BGM or custom suffixes
        if "_bgm" in filename:
            suffix += "_bgm"
        elif "_compare_bgm" in filename:
            suffix += "_compare_bgm"
            
        return f"{zh_base}{suffix}.{ext}"
    except Exception as e:
        print(f"  ⚠️ Warning in get_chinese_filename: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Upload audio/video files to Cloudflare R2")
    parser.add_argument("--dir", type=str, default="audio/qt", help="Local directory to scan (relative to repo root)")
    parser.add_argument("--bucket", type=str, default=DEFAULT_BUCKET, help="Cloudflare R2 Bucket name")
    parser.add_argument("--prefix", type=str, default="", help="Prefix path inside the bucket (e.g. media/)")
    parser.add_argument("--force", action="store_true", help="Force upload even if using wrangler (cannot check duplicate checks without boto3)")

    args = parser.parse_args()

    # Load account ID
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    # Read from ~/.secrets if available
    secrets_path = Path.home() / ".secrets"
    if secrets_path.exists():
        with open(secrets_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export CLOUDFLARE_ACCOUNT_ID="):
                    account_id = line.split("=", 1)[1].strip('"').strip("'")
                elif line.startswith("export R2_ACCESS_KEY_ID="):
                    access_key = line.split("=", 1)[1].strip('"').strip("'")
                elif line.startswith("export R2_SECRET_ACCESS_KEY="):
                    secret_key = line.split("=", 1)[1].strip('"').strip("'")

    if not account_id:
        print("❌ Error: CLOUDFLARE_ACCOUNT_ID not found in environment or ~/.secrets.")
        return 1

    source_dir = REPO_ROOT / args.dir
    if not source_dir.exists():
        print(f"❌ Error: Local directory '{source_dir}' does not exist.")
        return 1

    # Scan for MP3 and MP4 files
    files = list(source_dir.glob("*.mp3")) + list(source_dir.glob("*.mp4"))
    if not files:
        print(f"ℹ️  No MP3 or MP4 files found in {source_dir}")
        return 0

    print(f"🔍 Found {len(files)} files to upload to bucket '{args.bucket}'")

    use_boto3 = False
    if access_key and secret_key:
        try:
            import boto3
            use_boto3 = True
            print("✨ Found R2 API keys and boto3. Using high-speed S3 connection.")
        except ImportError:
            print("⚠️  R2 API keys found, but 'boto3' is not installed. Falling back to Wrangler CLI.")

    success_count = 0
    for f in sorted(files):
        # Construct key inside the bucket
        r2_key = f.name
        if args.prefix:
            prefix = args.prefix.rstrip("/")
            r2_key = f"{prefix}/{f.name}"
            
        success = False
        if use_boto3:
            download_name = get_chinese_filename(f.name)
            success = upload_via_boto3(account_id, access_key, secret_key, args.bucket, f, r2_key, download_name=download_name)
        else:
            success = upload_via_wrangler(args.bucket, f, r2_key)
            
        if success:
            success_count += 1

    print(f"\n🎉 Upload finished: {success_count}/{len(files)} files successfully processed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
