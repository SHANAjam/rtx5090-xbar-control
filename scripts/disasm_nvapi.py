#!/usr/bin/env python3
"""Disassemble RVAs from nvapi64_impl.dll using capstone.

Usage:
    python scripts/disasm_nvapi.py <dll> <rva_hex> <size_hex> [out.txt]
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone
import pefile


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    dll = Path(sys.argv[1])
    rva = int(sys.argv[2], 16)
    size = int(sys.argv[3], 16)
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    pe = pefile.PE(str(dll), fast_load=False)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    off = pe.get_offset_from_rva(rva)
    data = dll.read_bytes()[off:off + size]

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    lines = []
    for ins in md.disasm(data, image_base + rva):
        lines.append(f"{ins.address - image_base:08x}: {ins.mnemonic} {ins.op_str}")

    text = "\n".join(lines) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {len(lines)} instructions to {out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
