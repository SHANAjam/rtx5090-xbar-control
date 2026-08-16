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
PROP_RELS_BUFSIZE = 0x20000
PROP_RELS_MASK = 0xFF
PROP_ENTRY_BASE = 0x64
PROP_ENTRY_STRIDE = 0x108
PROP_OFF_RATIO = 0x04

DEFAULT_RATIO_RAW = 58976  # 0xE660 = 0.89990234375


def read_prop_rels(api: NvApi):
    buf = make_buffer(PROP_RELS_BUFSIZE)
    set_u32(buf, 0, PROP_RELS_VERSION)
    set_u32(buf, 4, PROP_RELS_MASK)
    rc = api.call(PROP_RELS_GET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"PropRelsGetControl failed rc={rc}")
    raw = get_u32(buf, PROP_ENTRY_BASE + PROP_OFF_RATIO)
    return buf, raw


def write_prop_rels(api: NvApi, raw_ratio: int):
    buf, old_raw = read_prop_rels(api)
    set_u32(buf, PROP_ENTRY_BASE + PROP_OFF_RATIO, raw_ratio & 0xFFFFFFFF)
    rc = api.call(PROP_RELS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"PropRelsSetControl failed rc={rc}")
    _, new_raw = read_prop_rels(api)
    return old_raw, new_raw


def ratio_raw_to_float(raw: int) -> float:
    return raw / 65536.0


def ratio_float_to_raw(ratio: float) -> int:
    if not (0.0 <= ratio <= 2.0):
        raise ValueError("ratio must be within 0.0..2.0")
    return int(round(ratio * 65536.0))
