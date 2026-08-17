#!/usr/bin/env python3
"""Run the complete multi-driver static validation in one go.

This is the single entry point for the R572..R610 validation described in
docs/DRIVER_VALIDATION.md. It checks:

  1. NvAPI ID table + version headers + GET_INFO layout
     (scripts/validate_nvapi_drivers.py)
  2. ClkDomains and VF entry/record offsets
     (scripts/derive_nvapi_offsets.py)

Usage:
    python scripts/run_full_validation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.derive_nvapi_offsets import BASE, VERSIONS, main as derive_main
from scripts.validate_nvapi_drivers import main as validate_main


def _dll_paths():
    paths = []
    for _version, folder, dll_name in VERSIONS:
        paths.append(str(BASE / folder / "Display.Driver" / dll_name))
    return paths


def main() -> int:
    print("=" * 70)
    print("FULL DRIVER VALIDATION")
    print("=" * 70)
    print("\n--- Part 1: NvAPI IDs, versions, GET_INFO layout ---\n")
    rc1 = validate_main(_dll_paths())
    print("\n--- Part 2: ClkDomains and VF offsets ---\n")
    rc2 = derive_main()
    print("\n" + "=" * 70)
    if rc1 == 0 and rc2 == 0:
        print("FULL VALIDATION: ALL OK")
        return 0
    print("FULL VALIDATION: SOME FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
