"""Clock domain control: XBAR frequency offset and XBAR-domain MSVDD offset.

Private NvAPI IDs:
  ClkDomainsGetControl 0xF58938F5
  ClkDomainsSetControl 0xD14B69CF
Version 0x000261A4 (V2) on the validated driver branch.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from .layout import find_repeating_dword_layout
from .nvapi import NvApi, get_u32, i32, make_buffer, set_u32

LOG = logging.getLogger("xbar5090.clk_domains")

CLK_DOMAINS_GET_CONTROL = 0xF58938F5
CLK_DOMAINS_SET_CONTROL = 0xD14B69CF
CLK_DOMAINS_VERSION = 0x000261A4
CLK_DOMAINS_BUFSIZE = 0x13000
CLK_DOMAINS_MASK = 0xFF
CLK_DOMAIN_ENTRY_STRIDE = 0x304
CLK_DOMAIN_ENTRY_BASE = 0x124
# XBAR domain index is an NvAPI clock-domain enum constant (Xbar=1), not a
# per-card layout guess. The entry base/stride are discovered live from the
# control buffer when possible.
XBAR_DOMAIN_INDEX = 1
OFF_FREQ_KHZ = 0x114
OFF_MSVDD_UV = 0x11C

_ENTRY_BASE = None
_ENTRY_STRIDE = None
_XBAR_DOMAIN_INDEX = None


def _profile_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "driver_profile.json")


def _profile_xbar_index():
    try:
        with open(_profile_path(), "r", encoding="utf-8") as f:
            profile = json.load(f)
        idx = profile.get("clk_domains", {}).get("xbar_domain_index")
        if isinstance(idx, int):
            return idx
    except Exception:
        pass
    return None


def _discover_layout_from_buf(buf):
    global _ENTRY_BASE, _ENTRY_STRIDE
    if _ENTRY_BASE is not None:
        return _ENTRY_BASE, _ENTRY_STRIDE
    layout = find_repeating_dword_layout(buf, 0x0F)
    if layout is not None:
        _ENTRY_BASE, _ENTRY_STRIDE = layout
    else:
        _ENTRY_BASE, _ENTRY_STRIDE = CLK_DOMAIN_ENTRY_BASE, CLK_DOMAIN_ENTRY_STRIDE
    return _ENTRY_BASE, _ENTRY_STRIDE


def entry_layout():
    """Return the discovered (entry_base, entry_stride), or validated defaults."""
    return (_ENTRY_BASE if _ENTRY_BASE is not None else CLK_DOMAIN_ENTRY_BASE,
            _ENTRY_STRIDE if _ENTRY_STRIDE is not None else CLK_DOMAIN_ENTRY_STRIDE)


def xbar_domain_index():
    """Return the XBAR domain index (discovered, profile, or API default)."""
    if _XBAR_DOMAIN_INDEX is not None:
        return _XBAR_DOMAIN_INDEX
    profile_idx = _profile_xbar_index()
    if profile_idx is not None:
        return profile_idx
    return XBAR_DOMAIN_INDEX


def _discover_xbar_index_from_buf(buf, entry_base, entry_stride):
    """If exactly one entry has a non-zero XBAR offset/MSVDD, use it as XBAR."""
    global _XBAR_DOMAIN_INDEX
    if _XBAR_DOMAIN_INDEX is not None:
        return _XBAR_DOMAIN_INDEX
    candidates = []
    for i in range(32):
        base = entry_base + i * entry_stride
        freq = get_u32(buf, base + OFF_FREQ_KHZ)
        msvdd = get_u32(buf, base + OFF_MSVDD_UV)
        if freq != 0 or msvdd != 0:
            candidates.append(i)
    if len(candidates) == 1:
        _XBAR_DOMAIN_INDEX = candidates[0]
        return _XBAR_DOMAIN_INDEX
    idx = xbar_domain_index()
    LOG.warning("XBAR domain index not discoverable from live buffer; using fallback %d", idx)
    return idx

# Physical frequency measurement (CLK_MEASURE_FREQ).
CLK_MEASURE_FREQ = 0x527FC458
CLK_MEASURE_VER = 0x1000C
CLK_MEASURE_MASK_OFF = 0x4
CLK_MEASURE_FREQ_OFF = 0x8
XBAR_MEASURE_MASK = 0x2


def measure_xbar_khz(api: NvApi) -> int:
    """Read the physical XBAR clock in kHz via CLK_MEASURE_FREQ."""
    buf = make_buffer(CLK_MEASURE_VER)
    set_u32(buf, 0, CLK_MEASURE_VER)
    set_u32(buf, CLK_MEASURE_MASK_OFF, XBAR_MEASURE_MASK)
    rc = api.call(CLK_MEASURE_FREQ, buf)
    if rc != 0:
        raise RuntimeError(f"CLK_MEASURE_FREQ failed rc={rc}")
    return get_u32(buf, CLK_MEASURE_FREQ_OFF)


def read_clock_domains(api: NvApi, get_id: int | None = None):
    buf = make_buffer(CLK_DOMAINS_BUFSIZE)
    set_u32(buf, 0, CLK_DOMAINS_VERSION)
    set_u32(buf, 8, CLK_DOMAINS_MASK)
    rc = api.call(get_id or CLK_DOMAINS_GET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"ClkDomainsGetControl failed rc={rc}")
    entry_base, entry_stride = _discover_layout_from_buf(buf)
    idx = _discover_xbar_index_from_buf(buf, entry_base, entry_stride)
    base = entry_base + idx * entry_stride
    freq = get_u32(buf, base + OFF_FREQ_KHZ)
    msvdd = get_u32(buf, base + OFF_MSVDD_UV)
    return buf, i32(freq), i32(msvdd)


def restore_from_buf(api: NvApi, buf) -> None:
    rc = api.call(CLK_DOMAINS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"ClkDomains restore failed rc={rc}")


def write_clock_domains(api: NvApi, freq_khz: int, msvdd_uv: int):
    buf, old_freq, old_msvdd = read_clock_domains(api)
    entry_base, entry_stride = entry_layout()
    base = entry_base + xbar_domain_index() * entry_stride
    set_u32(buf, base + OFF_FREQ_KHZ, freq_khz & 0xFFFFFFFF)
    set_u32(buf, base + OFF_MSVDD_UV, msvdd_uv & 0xFFFFFFFF)
    rc = api.call(CLK_DOMAINS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"ClkDomainsSetControl failed rc={rc}")
    _, new_freq, new_msvdd = read_clock_domains(api)
    return old_freq, old_msvdd, new_freq, new_msvdd
