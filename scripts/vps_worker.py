#!/usr/bin/env python3
import os
import requests
import subprocess
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRET_TOKEN = os.environ.get("VPS_WEBHOOK_SECRET", "change-me-securely")
MANAGER_URL = os.environ.get("TING_MANAGER_URL", "http://localhost:8080")

def generate_and_upload(plan_id: str):
    print(f"🚀 Starting audio generation for plan: {plan_id}")
    
    # Step 1: Run generate_plan_audio.py 4 times for different permutations
    # 1. Rotate Plain (1.0x voice, no BGM, no suffix)
    print("-> Running 1/4: Rotate Plain (1.0x, no BGM)")
    cmd_rotate_plain = [
        sys.executable, str(REPO_ROOT / "scripts" / "generate_plan_audio.py"),
        plan_id,
        "-o", f"audio/{plan_id}",
        "--speech-volume", "4",
        "--speed", "1.0",
        "--use-chapter-filename",
        "--no-speed-label",
        "--filename-suffix", "",
        "--filename-lang", "ascii"
    ]
    subprocess.run(cmd_rotate_plain, check=True, cwd=str(REPO_ROOT))

    # 2. Rotate BGM (1.5x voice + BGM, _bgm suffix)
    print("-> Running 2/4: Rotate BGM (1.5x + BGM)")
    cmd_rotate_bgm = [
        sys.executable, str(REPO_ROOT / "scripts" / "generate_plan_audio.py"),
        plan_id,
        "-o", f"audio/{plan_id}",
        "--speech-volume", "4",
        "--speed", "1.5",
        "--bgm",
        "--bgm-splits", "1",
        "--use-chapter-filename",
        "--no-speed-label",
        "--filename-suffix", "_bgm",
        "--filename-lang", "ascii"
    ]
    subprocess.run(cmd_rotate_bgm, check=True, cwd=str(REPO_ROOT))

    # 3. Compare Plain (1.0x compare voice, no BGM, _compare suffix)
    print("-> Running 3/4: Compare Plain (1.0x, no BGM)")
    cmd_compare_plain = [
        sys.executable, str(REPO_ROOT / "scripts" / "generate_plan_audio.py"),
        plan_id,
        "-o", f"audio/{plan_id}",
        "--speech-volume", "4",
        "--speed", "1.0",
        "--compare",
        "--use-chapter-filename",
        "--no-speed-label",
        "--filename-suffix", "_compare",
        "--filename-lang", "ascii"
    ]
    subprocess.run(cmd_compare_plain, check=True, cwd=str(REPO_ROOT))

    # 4. Compare BGM (1.5x compare voice + BGM, _compare_bgm suffix)
    print("-> Running 4/4: Compare BGM (1.5x + BGM)")
    cmd_compare_bgm = [
        sys.executable, str(REPO_ROOT / "scripts" / "generate_plan_audio.py"),
        plan_id,
        "-o", f"audio/{plan_id}",
        "--speech-volume", "4",
        "--speed", "1.5",
        "--bgm",
        "--bgm-splits", "1",
        "--compare",
        "--use-chapter-filename",
        "--no-speed-label",
        "--filename-suffix", "_compare_bgm",
        "--filename-lang", "ascii"
    ]
    subprocess.run(cmd_compare_bgm, check=True, cwd=str(REPO_ROOT))

    print(f"✅ Generated all 4 audio variations for {plan_id}")

    # Step 2: Upload to Cloudflare R2
    upload_cmd = [
        sys.executable, str(REPO_ROOT / "scripts" / "upload_to_r2.py"),
        "--dir", f"audio/{plan_id}",
        "--prefix", "qt",
        "--bucket", "shema-media"
    ]
    subprocess.run(upload_cmd, check=True, cwd=str(REPO_ROOT))
    print(f"✅ Uploaded audio files to Cloudflare R2")

    # Step 3: Update Plan Status in D1 Database to 'approved'
    d1_cmd = [
        "npx", "wrangler", "d1", "execute", "tingbible-db",
        "--remote",
        "--command", f"UPDATE reading_plans SET status = 'approved' WHERE id = '{plan_id}'"
    ]
    subprocess.run(d1_cmd, check=True, cwd=str(REPO_ROOT))
    print(f"🎉 Plan {plan_id} is now officially approved and live!")

    # Step 4: Clean up temporary audio files from VPS disk
    audio_dir = REPO_ROOT / "audio" / plan_id
    if audio_dir.exists():
        import shutil
        shutil.rmtree(audio_dir)
        print(f"🧹 Cleaned up temporary audio files at {audio_dir}")

def update_job_status(job_id: int, status: str, err_msg: str = None):
    headers = {
        "Authorization": f"Bearer {SECRET_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "job_id": job_id,
        "status": status,
        "error_message": err_msg
    }
    try:
        r = requests.post(f"{MANAGER_URL}/api/update-job", json=payload, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Failed to report job status to manager: {e}", file=sys.stderr)

def process_job(job_id: int, plan_id: str):
    try:
        generate_and_upload(plan_id)
        update_job_status(job_id, "completed")
        print(f"🎉 Job {job_id} ({plan_id}) completed successfully.")
    except Exception as e:
        err_msg = traceback.format_exc()
        print(f"❌ Job {job_id} ({plan_id}) failed: {e}", file=sys.stderr)
        update_job_status(job_id, "failed", err_msg)

        # Update database status to 'failed' in Cloudflare D1
        subprocess.run([
            "npx", "wrangler", "d1", "execute", "tingbible-db",
            "--remote",
            "--command", f"UPDATE reading_plans SET status = 'failed' WHERE id = '{plan_id}'"
        ], check=False, cwd=str(REPO_ROOT))

def main():
    print(f"Ting Queue Worker started. Polling manager URL: {MANAGER_URL}")
    headers = {"Authorization": f"Bearer {SECRET_TOKEN}"}
    
    while True:
        try:
            r = requests.get(f"{MANAGER_URL}/api/next-job", headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            
            if data.get("status") == "running":
                job_id = data["id"]
                plan_id = data["plan_id"]
                print(f"Picked up job via HTTP: ID={job_id}, Plan={plan_id}")
                process_job(job_id, plan_id)
            else:
                time.sleep(5)
        except KeyboardInterrupt:
            print("Worker shutting down.")
            break
        except Exception as e:
            print(f"Worker Loop Error (HTTP check failed): {e}", file=sys.stderr)
            time.sleep(10)

if __name__ == "__main__":
    main()
