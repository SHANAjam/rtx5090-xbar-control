"""Shared heuristics for discovering NvAPI buffer record layouts."""

from __future__ import annotations

from .nvapi import get_u32


def find_repeating_dword_layout(buf, value: int, min_offset: int = 0x100):
    """Find (base, stride) for repeated dword records in a buffer.

    Returns None if no plausible repeating layout is found. The stride is
    guarded to a plausible range to reduce false positives.
    """
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
