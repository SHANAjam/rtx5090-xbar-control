"""CLK_VF_POINTS: 127-point XBAR V/F status and control.

Private NvAPI IDs:
  INFO        0x8895B510  (RM 0x20809021)
  STATUS      0x7FEE9032  (RM 0x20809022)
  GET_CONTROL 0xDA025C3E  (RM 0x20809023)
  SET_CONTROL 0xFEC00D04  (RM 0x2080D024)
"""

from __future__ import annotations

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

    # Validated GB202 layout: 648 active flats, XBAR bank 127..253.
    if len(active) == 648 and active[0] == 0 and active[-1] == 647:
        return (127, 253)

    # Generic fallback: group into contiguous ranges and look for a 127-point
    # bank whose first record is XBAR type 0xD.
    buf = get_status(api, active, status_id=status_id)
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
            rec = STATUS_REC_BASE + s * STATUS_REC_STRIDE
            if get_u32(buf, rec) == 0xD:
                candidates.append((s, e))

    if not candidates:
        return None

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
    buf = make_buffer(VF_STATUS_VER)
    set_u32(buf, 0, VF_STATUS_VER)
    for i in active:
        off = 4 + 4 * (i // 32)
        set_u32(buf, off, get_u32(buf, off) | (1 << (i % 32)))
    rc = api.call(status_id, buf)
    if rc != 0:
        raise RuntimeError(f"VF_STATUS failed rc={rc}")
    return buf


def decode_status_record(buf, flat: int) -> dict:
    rec = STATUS_REC_BASE + flat * STATUS_REC_STRIDE
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
    buf = make_buffer(VF_CTRL_VER)
    set_u32(buf, 0, VF_CTRL_VER)
    for i in active:
        off = 4 + 4 * (i // 32)
        set_u32(buf, off, get_u32(buf, off) | (1 << (i % 32)))
    rc = api.call(get_id, buf)
    if rc != 0:
        raise RuntimeError(f"VF_GET_CONTROL failed rc={rc}")
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
    for flat in flats:
        rec = CTRL_REC_BASE + flat * CTRL_REC_STRIDE
        if get_u32(buf, rec) != 0xD:
            raise ValueError(f"flat {flat} is not XBAR type 0xD")
        set_u32(buf, rec + 0x24, 0)  # mode 0 = direct u32 offset
        set_u32(buf, rec + 0x38, freq_khz & 0xFFFFFFFF)
    set_control(api, buf, set_id=set_id)
    return get_control(api, active, get_id=get_id)
