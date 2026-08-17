"""GPC->XBAR propagation ratio control.

Private NvAPI IDs:
  PropRelsGetControl 0xCBFF71D0
  PropRelsSetControl 0xEF3D20EA
  PropRelsGetInfo    0xE826E4F0
Version 0x0001075C on the validated driver branch.
"""

from __future__ import annotations

from .nvapi import NvApi, get_u32, make_buffer, set_u32

PROP_RELS_GET_CONTROL = 0xCBFF71D0
PROP_RELS_SET_CONTROL = 0xEF3D20EA
PROP_RELS_GET_INFO = 0xE826E4F0
PROP_RELS_VERSION = 0x0001075C
PROP_RELS_GET_INFO_VER = 0x00015798
PROP_RELS_BUFSIZE = 0x20000
PROP_RELS_MASK = 0xFF
PROP_ENTRY_BASE = 0x64
PROP_ENTRY_STRIDE = 0x108
PROP_OFF_RATIO = 0x04

DEFAULT_RATIO_RAW = 58976  # 0xE660 = 0.89990234375


def validate_prop_rels(api: NvApi) -> bool:
    """Call GET_INFO first (safety step required by upstream LACT research)."""
    try:
        buf = make_buffer(PROP_RELS_GET_INFO_VER)
        set_u32(buf, 0, PROP_RELS_GET_INFO_VER)
        rc = api.call(PROP_RELS_GET_INFO, buf)
        return rc == 0
    except Exception:
        return False


def _find_ratio_offset(buf) -> int:
    """Fallback: locate the default ratio raw value in the control buffer."""
    for off in range(0, len(bytes(buf)) - 4, 4):
        if get_u32(buf, off) == DEFAULT_RATIO_RAW:
            return off
    return PROP_ENTRY_BASE + PROP_OFF_RATIO


def read_prop_rels_full(api: NvApi):
    buf = make_buffer(PROP_RELS_BUFSIZE)
    set_u32(buf, 0, PROP_RELS_VERSION)
    set_u32(buf, 4, PROP_RELS_MASK)
    rc = api.call(PROP_RELS_GET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"PropRelsGetControl failed rc={rc}")
    off = PROP_ENTRY_BASE + PROP_OFF_RATIO
    raw = get_u32(buf, off)
    if not (0 <= raw <= 2 * 65536):
        off = _find_ratio_offset(buf)
        raw = get_u32(buf, off)
    return buf, raw, off


def read_prop_rels(api: NvApi):
    buf, raw, _ = read_prop_rels_full(api)
    return buf, raw


def restore_from_buf(api: NvApi, buf) -> None:
    rc = api.call(PROP_RELS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"PropRels restore failed rc={rc}")


def write_prop_rels(api: NvApi, raw_ratio: int):
    buf, old_raw, off = read_prop_rels_full(api)
    set_u32(buf, off, raw_ratio & 0xFFFFFFFF)
    rc = api.call(PROP_RELS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"PropRelsSetControl failed rc={rc}")
    _, new_raw, _ = read_prop_rels_full(api)
    return old_raw, new_raw


def ratio_raw_to_float(raw: int) -> float:
    return raw / 65536.0


def ratio_float_to_raw(ratio: float) -> int:
    if not (0.0 <= ratio <= 2.0):
        raise ValueError("ratio must be within 0.0..2.0")
    # Use the hardware default raw value for 0.9 to avoid a 1-LSB mismatch.
    if abs(ratio - 0.9) < 1e-6:
        return DEFAULT_RATIO_RAW
    return int(round(ratio * 65536.0))
