"""Safety helpers: bounds, step limits, readback checks."""

from __future__ import annotations

# Hard absolute limits (still generous but bounded).
MAX_XBAR_FREQ_KHZ = 1_000_000
MAX_MSVDD_UV = 100_000
MAX_VF_STEP_KHZ = 15_000
MAX_XBAR_STEP_KHZ = 15_000
MAX_MSVDD_STEP_UV = 10_000

# Reference values from the author's RTX 5090 / driver 610.62/610.88.
# These are NOT universal validated ranges for all RTX 50-series cards.
AUTHOR_REF_XBAR_MIN_KHZ = 200_000
AUTHOR_REF_XBAR_MAX_KHZ = 235_000
AUTHOR_REF_MSVDD_MIN_UV = 0
AUTHOR_REF_MSVDD_MAX_UV = 10_000
AUTHOR_REF_RATIOS = (0.9, 1.0, 1.2)


def check_xbar_freq(freq_khz: int) -> None:
    if not (-MAX_XBAR_FREQ_KHZ <= freq_khz <= MAX_XBAR_FREQ_KHZ):
        raise ValueError("XBAR frequency offset out of range")


def check_msvdd(msvdd_uv: int) -> None:
    if not (-MAX_MSVDD_UV <= msvdd_uv <= MAX_MSVDD_UV):
        raise ValueError("MSVDD offset out of range")


def check_xbar_step(delta_khz: int) -> None:
    if abs(delta_khz) > MAX_XBAR_STEP_KHZ:
        raise ValueError(f"XBAR step too large: {delta_khz} > {MAX_XBAR_STEP_KHZ}")


def check_vf_step(delta_khz: int) -> None:
    if abs(delta_khz) > MAX_VF_STEP_KHZ:
        raise ValueError(f"VF step too large: {delta_khz} > {MAX_VF_STEP_KHZ}")


def check_msvdd_step(delta_uv: int) -> None:
    if abs(delta_uv) > MAX_MSVDD_STEP_UV:
        raise ValueError(f"MSVDD step too large: {delta_uv} > {MAX_MSVDD_STEP_UV}")


def is_author_reference_xbar(freq_khz: int) -> bool:
    return AUTHOR_REF_XBAR_MIN_KHZ <= freq_khz <= AUTHOR_REF_XBAR_MAX_KHZ


def is_author_reference_msvdd(msvdd_uv: int) -> bool:
    return AUTHOR_REF_MSVDD_MIN_UV <= msvdd_uv <= AUTHOR_REF_MSVDD_MAX_UV


def is_author_reference_ratio(ratio: float) -> bool:
    return any(abs(ratio - r) < 1e-6 for r in AUTHOR_REF_RATIOS)


def require_equal_readback(label: str, expected, actual) -> None:
    if expected != actual:
        raise RuntimeError(f"{label} readback mismatch: expected {expected}, got {actual}")
