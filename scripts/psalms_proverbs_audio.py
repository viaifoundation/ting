#!/usr/bin/env python3
"""Deprecated — use scripts/psprov.py (Psalms + Proverbs plan CLI)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "psprov.py"


def main() -> int:
    print(
        "Note: psalms_proverbs_audio.py forwards to scripts/psprov.py",
        file=sys.stderr,
    )
    return subprocess.run([sys.executable, str(_SCRIPT), *sys.argv[1:]]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
