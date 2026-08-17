"""Minimal driver/gpu validation for write safety."""

from __future__ import annotations

import json
import os
import subprocess
import sys

VALIDATED_DRIVER_PREFIX = "610.62"
# Prefixes verified by the driver auto-crack (same NvAPI IDs/read layout).
VALIDATED_DRIVER_PREFIXES = ["610.62", "610.88"]


def get_driver_version() -> str:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def get_gpu_name() -> str:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def ensure_supported_gpu() -> tuple[bool, str]:
    name = get_gpu_name()
    if not name:
        return False, "Could not read GPU name from nvidia-smi."
    if "RTX 5090" not in name:
        return False, f"Unsupported GPU: {name}. Only RTX 5090 is validated."
    return True, f"GPU {name} is supported."


def _profile_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "driver_profile.json")


def _profile_allows(version: str) -> bool:
    try:
        with open(_profile_path(), "r", encoding="utf-8") as f:
            profile = json.load(f)
        return bool(profile.get("probe_ok")) and profile.get("detected_driver") == version
    except Exception:
        return False


def ensure_supported_driver() -> tuple[bool, str]:
    version = get_driver_version()
    if not version:
        return False, "Could not read driver version from nvidia-smi."
    if any(version.startswith(p) for p in VALIDATED_DRIVER_PREFIXES):
        return True, f"Driver {version} is in the validated family."
    if _profile_allows(version):
        return True, f"Driver {version} is allowed by driver_profile.json (probe/crack verified)."
    return False, (
        f"Unsupported driver: {version}. "
        f"Validated driver prefixes: {', '.join(VALIDATED_DRIVER_PREFIXES)}. "
        "No matching driver_profile.json found. Refusing to write."
    )
