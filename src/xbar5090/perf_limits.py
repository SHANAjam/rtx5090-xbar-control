"""PERF limits V2 read-only access (RM 0x2080A079).

Private NvAPI ID 0xEFCEDD1F, version 0x0007388C on the validated branch.
This module intentionally does NOT expose SET: the RM SET command
0x2080E0AF was not found in the validated nvapi64_impl.dll.
"""

from __future__ import annotations

from .nvapi import NvApi, get_u32, make_buffer, set_u32

PERF_GET = 0xEFCEDD1F
PERF_VER = 0x0007388C
# Explicit buffer size; do not assume it always equals the version header.
PERF_SIZE = 0x0007388C

# User-facing IDs for XBAR max/min on the validated branch.
XBAR_MAX_USER_ID = 0xD6
XBAR_MIN_USER_ID = 0xD9


def get_perf_limits(api: NvApi, user_ids=None, count: int = 0):
    """Call PERF GET.

    count=0 enumerates all limit IDs. To query specific IDs, pass a list of
    user-facing IDs and set count=len(user_ids).
    """
    buf = make_buffer(PERF_SIZE)
    set_u32(buf, 0, PERF_VER)
    if user_ids:
        if count != len(user_ids):
            raise ValueError("count must equal len(user_ids)")
        set_u32(buf, 8, count)
        for i, uid in enumerate(user_ids):
            set_u32(buf, 0xC + i * 0x338, uid & 0xFFFFFFFF)
    rc = api.call(PERF_GET, buf)
    if rc != 0:
        raise RuntimeError(f"PERF_GET failed rc={rc}")
    return buf


def find_entry_by_user_id(buf, uid: int):
    for i in range(0, (PERF_SIZE - 0xC) // 0x338):
        base = 0xC + i * 0x338
        if get_u32(buf, base) == uid:
            return base
    return None


def parse_entries(buf):
    """Parse all PERF limit entries into a list of dicts."""
    entries = []
    for i in range(0, (PERF_SIZE - 0xC) // 0x338):
        base = 0xC + i * 0x338
        uid = get_u32(buf, base)
        if uid == 0:
            continue
        entries.append({
            "index": i,
            "user_id": uid,
            "base": base,
            "values": [get_u32(buf, base + o) for o in range(0, 0x40, 4)],
        })
    return entries
