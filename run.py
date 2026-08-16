#!/usr/bin/env python3
"""Simple launcher for xbar5090.

Usage:
    python run.py status
    python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000
    python run.py set-ratio --ratio 1.2
    python run.py vfp-set-range --start 225 --end 245 --freq-khz 88000
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from xbar5090.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
