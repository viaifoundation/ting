#!/usr/bin/env python3
"""
Backward-compatible entry point. Use psprov.py instead.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "psprov.py"


def main() -> int:
    print(
        "Note: praise90.py is deprecated; use scripts/psprov.py",
        file=sys.stderr,
    )
    p = subprocess.run([sys.executable, str(_SCRIPT), *sys.argv[1:]])
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
