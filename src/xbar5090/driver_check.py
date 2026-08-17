"""Minimal driver/gpu validation for write safety."""

from __future__ import annotations

import json
import os
import subprocess
import sys

VALIDATED_DRIVER_PREFIX = "610.62"
# Prefixes verified by static cross-version analysis (same NvAPI IDs, version
# headers, GET_INFO relationship layout, ClkDomains entry offsets, and VF
# record offsets). See docs/DRIVER_VALIDATION.md.
VALIDATED_DRIVER_PREFIXES = [
    "572.16", "576.02", "580.88", "581.42",
    "591.86", "596.49", "610.62", "610.88",
]


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


# Known desktop and laptop RTX 50-series models. Unknown models that still
# contain "RTX 50" are allowed only after explicit user confirmation.
KNOWN_RTX50_MODELS = [
    "RTX 5050",
    "RTX 5060",
    "RTX 5060 Ti",
    "RTX 5070",
    "RTX 5070 Ti",
    "RTX 5080",
    "RTX 5090",
    "RTX 5090 D",
    "RTX 5090 D v2",
    "RTX 5050 Laptop GPU",
    "RTX 5060 Laptop GPU",
    "RTX 5070 Laptop GPU",
    "RTX 5070 Ti Laptop GPU",
    "RTX 5080 Laptop GPU",
    "RTX 5090 Laptop GPU",
]


def is_known_rtx50(name: str) -> bool:
    return any(model.lower() in name.lower() for model in KNOWN_RTX50_MODELS)


# All desktop/laptop RTX 50-series models use the same private NvAPI layout
# (validated on R572..R610). This is intentionally broad; unknown RTX 50
# models are allowed only after confirmation in the CLI.
def ensure_supported_gpu() -> tuple[bool, str]:
    name = get_gpu_name()
    if not name:
        return False, "Could not read GPU name from nvidia-smi."
    lower = name.lower()
    if "rtx 50" not in lower:
        return False, f"Unsupported GPU: {name}. Only RTX 50-series is supported."
    return True, f"GPU {name} is supported (RTX 50 family, desktop or laptop)."


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
