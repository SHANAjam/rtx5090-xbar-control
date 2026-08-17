"""Minimal driver/gpu validation for write safety."""

from __future__ import annotations

import subprocess

VALIDATED_DRIVER_PREFIX = "610.62"


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


def ensure_supported_driver() -> tuple[bool, str]:
    version = get_driver_version()
    if not version:
        return False, "Could not read driver version from nvidia-smi."
    if not version.startswith(VALIDATED_DRIVER_PREFIX):
        return False, (
            f"Unsupported driver: {version}. "
            f"Validated driver prefix: {VALIDATED_DRIVER_PREFIX}. "
            "Refusing to write."
        )
    return True, f"Driver {version} is in the validated family."
