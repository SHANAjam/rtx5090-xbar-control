"""Safety helpers: bounds, step limits, readback checks."""

from __future__ import annotations

MAX_XBAR_FREQ_KHZ = 1_000_000
MAX_MSVDD_UV = 100_000
MAX_VF_STEP_KHZ = 15_000
MAX_MSVDD_STEP_UV = 10_000


def check_xbar_freq(freq_khz: int) -> None:
    if not (-MAX_XBAR_FREQ_KHZ <= freq_khz <= MAX_XBAR_FREQ_KHZ):
        raise ValueError("XBAR frequency offset out of range")


def check_msvdd(msvdd_uv: int) -> None:
    if not (-MAX_MSVDD_UV <= msvdd_uv <= MAX_MSVDD_UV):
        raise ValueError("MSVDD offset out of range")


def check_vf_step(delta_khz: int) -> None:
    if abs(delta_khz) > MAX_VF_STEP_KHZ:
        raise ValueError(f"VF step too large: {delta_khz} > {MAX_VF_STEP_KHZ}")


def check_msvdd_step(delta_uv: int) -> None:
    if abs(delta_uv) > MAX_MSVDD_STEP_UV:
        raise ValueError(f"MSVDD step too large: {delta_uv} > {MAX_MSVDD_STEP_UV}")


def require_equal_readback(label: str, expected, actual) -> None:
    if expected != actual:
        raise RuntimeError(f"{label} readback mismatch: expected {expected}, got {actual}")
