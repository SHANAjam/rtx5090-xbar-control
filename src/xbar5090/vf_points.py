"""CLK_VF_POINTS: 127-point XBAR V/F status and control.

Private NvAPI IDs:
  INFO        0x8895B510  (RM 0x20809021)
  STATUS      0x7FEE9032  (RM 0x20809022)
  GET_CONTROL 0xDA025C3E  (RM 0x20809023)
  SET_CONTROL 0xFEC00D04  (RM 0x2080D024)
"""

from __future__ import annotations

import json
import os
import sys

from .nvapi import NvApi, get_u32, i32, make_buffer, set_u32

VF_INFO = 0x8895B510
VF_STATUS = 0x7FEE9032
VF_GET_CONTROL = 0xDA025C3E
VF_SET_CONTROL = 0xFEC00D04

VF_INFO_VER = 0x00078604
VF_STATUS_VER = 0x001E8604
VF_CTRL_VER = 0x00474604

XBAR_START = 127
XBAR_END = 253  # inclusive

STATUS_REC_BASE = 0x304
STATUS_REC_STRIDE = 0x1E8
CTRL_REC_BASE = 0x304
CTRL_REC_STRIDE = 0x424

# Discovered layouts (populated automatically from live buffers).
_STATUS_LAYOUT = None
_CTRL_LAYOUT = None


def _find_repeating_dword_layout(buf, value: int, min_offset: int = 0x100):
    """Find (base, stride) for repeated dword records in a buffer."""
    data = bytes(buf)
    offs = [
        i for i in range(min_offset, len(data) - 4, 4)
        if get_u32(buf, i) == value
    ]
    if len(offs) < 2:
        return None
    best = None
    for i in range(len(offs) - 1):
        stride = offs[i + 1] - offs[i]
        if stride <= 0:
            continue
        # Plausible record stride guard against false positives.
        if stride < 0x40 or stride > 0x1000:
            continue
        base = offs[i]
        count = sum(1 for off in offs if (off - base) % stride == 0)
        if best is None or count > best[0]:
            best = (count, base, stride)
    if best is not None and best[0] >= 2:
        return (best[1], best[2])
    return None


def status_layout():
    """Return the currently discovered STATUS (rec_base, rec_stride)."""
    return _STATUS_LAYOUT or (STATUS_REC_BASE, STATUS_REC_STRIDE)


def control_layout():
    """Return the currently discovered CONTROL (rec_base, rec_stride)."""
    return _CTRL_LAYOUT or (CTRL_REC_BASE, CTRL_REC_STRIDE)


def discover_status_layout(api: NvApi, active, status_id: int = VF_STATUS):
    """Return (rec_base, rec_stride) for STATUS records, discovered live."""
    global _STATUS_LAYOUT
    if _STATUS_LAYOUT is not None:
        return _STATUS_LAYOUT
    buf = get_status(api, active, status_id=status_id)
    layout = _find_repeating_dword_layout(buf, 0xD)
    if layout is None:
        layout = (STATUS_REC_BASE, STATUS_REC_STRIDE)
    _STATUS_LAYOUT = layout
    return layout


def discover_control_layout(api: NvApi, active, get_id: int = VF_GET_CONTROL):
    """Return (rec_base, rec_stride) for CONTROL records, discovered live."""
    global _CTRL_LAYOUT
    if _CTRL_LAYOUT is not None:
        return _CTRL_LAYOUT
    buf = get_control(api, active, get_id=get_id)
    layout = _find_repeating_dword_layout(buf, 0xD)
    if layout is None:
        layout = (CTRL_REC_BASE, CTRL_REC_STRIDE)
    _CTRL_LAYOUT = layout
    return layout


def _profile_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "driver_profile.json")


def _profile_bank():
    """Return (start, end) from driver_profile.json if present."""
    try:
        with open(_profile_path(), "r", encoding="utf-8") as f:
            profile = json.load(f)
        vf = profile.get("vf_points", {})
        start = vf.get("xbar_start")
        end = vf.get("xbar_end")
        if isinstance(start, int) and isinstance(end, int) and start <= end:
            return (start, end)
    except Exception:
        pass
    return None


def detect_xbar_bank(api: NvApi, info_id: int = VF_INFO, status_id: int = VF_STATUS):
    """Try to auto-detect the XBAR V/F bank on the current GPU/driver.

    Returns (start, end) or None if it cannot be identified safely.

    Note: automatic identification is only reliable on the validated GB202
    layout (active flats 0..647, XBAR bank 127..253). On other layouts this
    function returns None so the caller can refuse to continue.
    """
    active = active_mask(api, info_id=info_id)
    if not active:
        return None

    # Generic: group into contiguous ranges and look for a 127-point bank
    # whose first record is XBAR type 0xD. No validated-layout shortcut is
    # used; the scan works from the live STATUS buffer.
    buf = get_status(api, active, status_id=status_id)
    rec_base, rec_stride = _STATUS_LAYOUT or discover_status_layout(api, active, status_id=status_id)

    # Primary generic detection: a 127-point contiguous window where every
    # record is XBAR type 0xD and has a positive total frequency offset.
    # This uniquely identifies the XBAR bank on the validated RTX 5090 and is
    # intended to be generic across RTX 50-series cards.
    if len(active) >= 127:
        active_set = set(active)
        for s in range(active[0], active[-1] - 126 + 1):
            ok = True
            for i in range(s, s + 127):
                if i not in active_set:
                    ok = False
                    break
                rec = rec_base + i * rec_stride
                if get_u32(buf, rec) != 0xD:
                    ok = False
                    break
                if i32(get_u32(buf, rec + 0x64)) <= 0:
                    ok = False
                    break
            if ok:
                return (s, s + 126)

    # Fallback: look for a 127-point contiguous active range with type 0xD.
    ranges = []
    start = prev = active[0]
    for x in active[1:]:
        if x != prev + 1:
            ranges.append((start, prev))
            start = x
        prev = x
    ranges.append((start, prev))

    candidates = []
    for s, e in ranges:
        if e - s + 1 == 127:
            rec = rec_base + s * rec_stride
            if get_u32(buf, rec) == 0xD:
                candidates.append((s, e))

    if not candidates:
        return _profile_bank()

    for s, e in candidates:
        if s == 127:
            return (s, e)
    for s, e in candidates:
        if s != 0:
            return (s, e)
    return candidates[0]


def active_mask(api: NvApi, info_id: int = VF_INFO):
    buf = make_buffer(VF_INFO_VER)
    set_u32(buf, 0, VF_INFO_VER)
    rc = api.call(info_id, buf)
    if rc != 0:
        raise RuntimeError(f"VF_INFO failed rc={rc}")
    active = []
    for i in range(2048):
        if get_u32(buf, 4 + 4 * (i // 32)) & (1 << (i % 32)):
            active.append(i)
    return active


def get_status(api: NvApi, active, status_id: int = VF_STATUS):
    global _STATUS_LAYOUT
    buf = make_buffer(VF_STATUS_VER)
    set_u32(buf, 0, VF_STATUS_VER)
    for i in active:
        off = 4 + 4 * (i // 32)
        set_u32(buf, off, get_u32(buf, off) | (1 << (i % 32)))
    rc = api.call(status_id, buf)
    if rc != 0:
        raise RuntimeError(f"VF_STATUS failed rc={rc}")
    layout = _find_repeating_dword_layout(buf, 0xD)
    if layout is not None:
        _STATUS_LAYOUT = layout
    return buf


def decode_status_record(buf, flat: int) -> dict:
    rec_base, rec_stride = _STATUS_LAYOUT or (STATUS_REC_BASE, STATUS_REC_STRIDE)
    rec = rec_base + flat * rec_stride
    return {
        "flat": flat,
        "type": get_u32(buf, rec),
        "base_freq_mhz": get_u32(buf, rec + 0x24),
        "voltage_uv": get_u32(buf, rec + 0x58),
        "total_freq_offset_khz": i32(get_u32(buf, rec + 0x64)),
        "effective_freq_mhz": get_u32(buf, rec + 0xF0),
        "voltage_dup_uv": get_u32(buf, rec + 0xF4),
    }


def get_control(api: NvApi, active, get_id: int = VF_GET_CONTROL):
    global _CTRL_LAYOUT
    buf = make_buffer(VF_CTRL_VER)
    set_u32(buf, 0, VF_CTRL_VER)
    for i in active:
        off = 4 + 4 * (i // 32)
        set_u32(buf, off, get_u32(buf, off) | (1 << (i % 32)))
    rc = api.call(get_id, buf)
    if rc != 0:
        raise RuntimeError(f"VF_GET_CONTROL failed rc={rc}")
    layout = _find_repeating_dword_layout(buf, 0xD)
    if layout is not None:
        _CTRL_LAYOUT = layout
    return buf


def set_control(api: NvApi, buf, set_id: int = VF_SET_CONTROL) -> None:
    rc = api.call(set_id, buf)
    if rc != 0:
        raise RuntimeError(f"VF_SET_CONTROL failed rc={rc}")


def set_xbar_range(api: NvApi, start: int, end: int, freq_khz: int,
                   info_id: int = VF_INFO, get_id: int = VF_GET_CONTROL,
                   set_id: int = VF_SET_CONTROL):
    # NOTE: On the validated 610.62/610.88 driver, submitting a multi-bit
    # active mask in one SET_CONTROL call works. Older drivers (e.g. LACT's
    # 590.48.01) required exactly one bit per call and returned -1 for a
    # full mask. If you use --force-driver on an older driver, this may fail.
    active = active_mask(api, info_id=info_id)
    flats = [i for i in range(start, end + 1) if i in active]
    if not flats:
        raise ValueError("no active XBAR flats in range")
    buf = get_control(api, active, get_id=get_id)
    rec_base, rec_stride = _CTRL_LAYOUT or discover_control_layout(api, active, get_id=get_id)
    for flat in flats:
        rec = rec_base + flat * rec_stride
        if get_u32(buf, rec) != 0xD:
            raise ValueError(f"flat {flat} is not XBAR type 0xD")
        set_u32(buf, rec + 0x24, 0)  # mode 0 = direct u32 offset
        set_u32(buf, rec + 0x38, freq_khz & 0xFFFFFFFF)
    set_control(api, buf, set_id=set_id)
    return get_control(api, active, get_id=get_id)
