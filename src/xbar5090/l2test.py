"""XBAR L2 data-integrity test runner (bundled CUDA checker).

This module runs the L2 checker from LACT #1147 comment 3 and reports whether
the current XBAR configuration is stable (zero L2 errors and no new
nvlddmkm/Xid events).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time


def _checker_path() -> str:
    if getattr(sys, "frozen", False):
        # PyInstaller bundles data under sys._MEIPASS.
        return os.path.join(sys._MEIPASS, "xbar5090", "data", "xbar_l2_check.exe")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "xbar_l2_check.exe")


def _get_new_nvlddmkm(start_local_str: str) -> list[str]:
    ps = (
        "$s = [datetime]::Parse('{0}'); "
        "Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='nvlddmkm'; StartTime=$s}} "
        "-ErrorAction SilentlyContinue | ForEach-Object {{ \"$($_.TimeCreated.ToString('o'))|$($_.Id)\" }}"
    ).format(start_local_str)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except Exception as e:
        return ["<event query failed: %s>" % e]


def _run_round(mode: str, blocks: int, threads: int, stress_iters: int) -> dict:
    exe = _checker_path()
    if not os.path.exists(exe):
        return {"error": f"L2 checker not found: {exe}"}
    cmd = [exe, "--blocks", str(blocks), "--threads", str(threads), "--rounds", "1", "--mode", mode]
    if mode == "load":
        cmd += ["--stress-iters", str(stress_iters)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    m = re.search(r"errors=(\d+)\s+elapsed_ms=([\d.]+)", p.stdout or "")
    if p.returncode != 0 or not m:
        return {"error": (p.stderr or p.stdout or "").strip(), "returncode": p.returncode}
    return {"errors": int(m.group(1)), "elapsed_ms": float(m.group(2))}


def _gpu_blocks() -> int:
    """Pick a reasonable block count for the detected RTX 50-series GPU."""
    try:
        from . import driver_check
        name = driver_check.get_gpu_name().lower()
    except Exception:
        name = ""
    table = [
        ("5090", 1360),
        ("5080", 800),
        ("5070 ti", 640),
        ("5070", 480),
        ("5060 ti", 384),
        ("5060", 320),
        ("5050", 256),
    ]
    for key, blocks in table:
        if key in name:
            return blocks
    return 1360


def run_l2_test(blocks: int | None = None, threads: int = 256,
                stress_iters: int = 100000,
                idle_rounds: int = 3, load_rounds: int = 3) -> bool:
    """Run the L2 integrity test. Returns True only if all rounds pass."""
    if blocks is None:
        blocks = _gpu_blocks()
    print("=== XBAR L2 stability test ===")
    print("Using checker:", _checker_path())
    print(f"Using blocks={blocks} threads={threads} (auto-selected if not specified)")
    start_local = time.strftime("%Y-%m-%dT%H:%M:%S")
    all_ok = True
    errors_total = 0
    for mode, rounds in (("idle", idle_rounds), ("load", load_rounds)):
        for i in range(rounds):
            row = _run_round(mode, blocks, threads, stress_iters)
            if "error" in row:
                print(f"  round {i+1} {mode}: ERROR {row['error']}")
                all_ok = False
            else:
                print(f"  round {i+1} {mode}: errors={row['errors']} elapsed_ms={row['elapsed_ms']:.1f}")
                errors_total += row["errors"]
                if row["errors"] != 0:
                    all_ok = False
    new_events = _get_new_nvlddmkm(start_local)
    print("New nvlddmkm/Xid events:", len(new_events))
    for ev in new_events:
        print("  ", ev)
    if new_events:
        all_ok = False
    print("Total L2 errors:", errors_total)
    print("RESULT:", "PASS" if all_ok else "FAIL")
    return all_ok
