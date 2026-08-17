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


# GET_INFO relationship-entry layout decoded from nvapi64_impl.dll (610.62/610.88).
#
# Each GET_INFO record is a 0x150-byte block; only the first 16 bytes are
# consumed by the NvAPI wrapper:
#   +0x00  u32  relationship type (Windows mapped type; Linux raw type = this + 3)
#   +0x04  u8   source clock-domain index (0 = GPC, 1 = XBAR, 2 = SYS, ...)
#   +0x05  u8   destination clock-domain index
#   +0x06  u8   bidirectional flag
#   +0x07  u8   padding (zero)
#   +0x08  u32  ratio in U16.16 format (type 0 only; 0 = GPC->XBAR ratio)
#   +0x0C  u32  inverse ratio in U16.16 format (type 0 only)
#
# The Windows "mapped type" is produced by a small dispatcher in the driver:
# raw Linux type 3 -> Windows type 0, 4 -> 1, 5 -> 2, 6 -> 3, 7 -> 4.
PROP_INFO_REC_BASE = 0x8E8
PROP_INFO_REC_STRIDE = 0x150
PROP_INFO_OFF_TYPE = 0x00
PROP_INFO_OFF_SRC = 0x04
PROP_INFO_OFF_DST = 0x05
PROP_INFO_OFF_BIDIR = 0x06
PROP_INFO_OFF_RATIO = 0x08
PROP_INFO_OFF_INV_RATIO = 0x0C

# Validated GPC->XBAR propagation-ratio relationship on RTX 5090 / R610.
# Windows mapped type 0 == Linux raw type 3.
PROP_RELS_TYPE_GPC_XBAR = 0
PROP_RELS_SRC_GPC = 0
PROP_RELS_DST_XBAR = 1
PROP_RELS_BIDIR = 1


def get_prop_rels_info(api: NvApi):
    """Call PropRelsGetInfo and return the raw GET_INFO buffer."""
    info = make_buffer(PROP_RELS_GET_INFO_VER)
    set_u32(info, 0, PROP_RELS_GET_INFO_VER)
    rc = api.call(PROP_RELS_GET_INFO, info)
    if rc != 0:
        raise RuntimeError(f"PropRelsGetInfo failed rc={rc}")
    return info


def decode_prop_rel_info(buf) -> list[dict]:
    """Parse GET_INFO relationship records into typed dictionaries."""
    count = get_u32(buf, 4)
    records = []
    for i in range(count):
        off = PROP_INFO_REC_BASE + i * PROP_INFO_REC_STRIDE
        records.append({
            "index": i,
            "type": get_u32(buf, off + PROP_INFO_OFF_TYPE),
            "src": get_u32(buf, off + PROP_INFO_OFF_SRC) & 0xFF,
            "dst": get_u32(buf, off + PROP_INFO_OFF_DST) & 0xFF,
            "bidir": get_u32(buf, off + PROP_INFO_OFF_BIDIR) & 0xFF,
            "ratio_raw": get_u32(buf, off + PROP_INFO_OFF_RATIO),
            "inverse_ratio_raw": get_u32(buf, off + PROP_INFO_OFF_INV_RATIO),
        })
    return records


def find_xbar_ratio_record(records: list[dict]) -> dict | None:
    """Return the GPC->XBAR propagation-ratio record, or None."""
    for rec in records:
        if (rec["type"] == PROP_RELS_TYPE_GPC_XBAR
                and rec["src"] == PROP_RELS_SRC_GPC
                and rec["dst"] == PROP_RELS_DST_XBAR
                and rec["bidir"] == PROP_RELS_BIDIR):
            return rec
    return None


def find_xbar_ratio_record_in_buffer(buf) -> dict | None:
    """Scan the GET_INFO buffer for the GPC->XBAR record without hardcoded offsets.

    A valid record has:
      +0x00 u32 type == 0
      +0x04 u8  src == 0
      +0x05 u8  dst == 1
      +0x06 u8  bidir == 1
      +0x08 u32 ratio_raw == DEFAULT_RATIO_RAW
    """
    data = bytes(buf)
    for off in range(0, len(data) - 16, 4):
        if get_u32(buf, off) != PROP_RELS_TYPE_GPC_XBAR:
            continue
        if data[off + PROP_INFO_OFF_SRC] != PROP_RELS_SRC_GPC:
            continue
        if data[off + PROP_INFO_OFF_DST] != PROP_RELS_DST_XBAR:
            continue
        if data[off + PROP_INFO_OFF_BIDIR] != PROP_RELS_BIDIR:
            continue
        if get_u32(buf, off + PROP_INFO_OFF_RATIO) != DEFAULT_RATIO_RAW:
            continue
        return {
            "index": None,
            "type": PROP_RELS_TYPE_GPC_XBAR,
            "src": PROP_RELS_SRC_GPC,
            "dst": PROP_RELS_DST_XBAR,
            "bidir": PROP_RELS_BIDIR,
            "ratio_raw": DEFAULT_RATIO_RAW,
            "inverse_ratio_raw": get_u32(buf, off + PROP_INFO_OFF_INV_RATIO),
        }
    return None


def validate_prop_rels(api: NvApi) -> bool:
    """Strict GET_INFO + GET_CONTROL validation before any ratio write.

    Per the upstream LACT guidance, a write is only allowed if:
      1. GET_INFO returns success and its version header matches.
      2. GET_INFO contains a valid GPC->XBAR relationship
         (type=3 Linux / mapped type=0, src=0, dst=1, bidir=1).
      3. That relationship's default ratio raw is 0xE660 (0.9).
      4. GET_CONTROL returns success with the expected version header.

    If any check fails, this returns False and the caller must refuse to
    write unless the user explicitly used --force-driver.
    """
    try:
        info = get_prop_rels_info(api)
        if get_u32(info, 0) != PROP_RELS_GET_INFO_VER:
            return False

        rec = find_xbar_ratio_record_in_buffer(info)
        if rec is None:
            return False

        ctrl = make_buffer(PROP_RELS_BUFSIZE)
        set_u32(ctrl, 0, PROP_RELS_VERSION)
        set_u32(ctrl, 4, PROP_RELS_MASK)
        rc = api.call(PROP_RELS_GET_CONTROL, ctrl)
        if rc != 0:
            return False
        if get_u32(ctrl, 0) != PROP_RELS_VERSION:
            return False
        return True
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
