#!/usr/bin/env python3
"""Statically derive ClkDomains and VF entry offsets across driver versions.

For each DLL, locate the real functions and disassemble them, then check for
the offset constants used by the project:

ClkDomains:
  CLK_GET:  entry base 0x124, stride 0x304, freq +0x114, MSVDD +0x11C
  CLK_SET:  should contain stride 0x304 (loop)
VF:
  VF_STATUS: status rec base 0x304, stride 0x1E8, fields +0x24/+0x58/+0x64/+0xF0
  VF_GET:    control rec base 0x304, stride 0x424, offset +0x38
  VF_SET:    same as VF_GET

Usage:
    python scripts/derive_nvapi_offsets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.validate_nvapi_drivers import find_table_records, load_pe, disasm_function

BASE = Path(r"D:\迅雷下载\1")
VERSIONS = [
    ("572.16", "572.16-desktop-win10-win11-64bit-international-dch-whql", "nvapi64.dll"),
    ("576.02", "576.02-desktop-win10-win11-64bit-international-dch-whql", "nvapi64.dll"),
    ("580.88", "580.88-desktop-win10-win11-64bit-international-dch-whql", "nvapi64.dll"),
    ("581.42", "581.42-desktop-win10-win11-64bit-international-dch-whql", "nvapi64.dll"),
    ("591.86", "591.86-desktop-win10-win11-64bit-international-dch-whql", "nvapi64.dll"),
    ("596.49", "596.49-desktop-win10-win11-64bit-international-dch-whql", "nvapi64.dll"),
    ("610.62", "610.62-desktop-win10-win11-64bit-international-dch-whql", "nvapi64_impl.dll"),
    ("610.88", "610.88-desktop-win10-win11-64bit-international-dch-whql", "nvapi64_impl.dll"),
]

# The absolute offsets are often encoded as base+relative in older DLLs, so we
# check for the address-arithmetic markers that prove the same layout:
#   CLK_GET: lea rdi,[buf+0x234]; entry base = buf+0x124; stride 0x304
#   VF_STATUS: lea rsi,[buf+0x37c]; rec base = buf+0x304; stride 0x1E8
#   VF_GET/SET: lea rbx,[buf+0x328]; rec base = buf+0x304; stride 0x424
# Each function has multiple equivalent marker groups because older DLLs use
# base+relative addressing while newer DLLs use absolute offsets.
FUNCS = {
    "CLK_GET": (0xF58938F5, [
        ["0x124", "0x304", "0x114", "0x11c"],  # newer absolute
        ["0x234", "0x304"],                    # older relative
    ]),
    "CLK_SET": (0xD14B69CF, [
        ["0x304"],
    ]),
    "VF_STATUS": (0x7FEE9032, [
        ["0x304", "0x1e8", "0x24", "0x58", "0x64", "0xf0"],  # newer absolute
        ["0x37c", "0x1e8", "0x78"],                          # older relative
    ]),
    "VF_GET": (0xDA025C3E, [
        ["0x304", "0x424", "0x38"],   # newer absolute
        ["0x328", "0x424", "0x24", "0x14"],  # older relative
    ]),
    "VF_SET": (0xFEC00D04, [
        ["0x304", "0x424", "0x38"],   # newer absolute
        ["0x33c", "0x424", "0x38"],   # older relative
    ]),
}


def contains_all(insns, needles):
    text = "\n".join(f"{i.mnemonic} {i.op_str}" for i in insns).lower()
    return {n: (n.lower() in text) for n in needles}


def group_ok(insns, groups):
    """Return (ok, missing_list) if any marker group is fully present."""
    for group in groups:
        found = contains_all(insns, group)
        if all(found.values()):
            return True, []
    # Report the missing needles from the first group (for diagnostics).
    found = contains_all(insns, groups[0])
    return False, [k for k, v in found.items() if not v]


def main(argv=None) -> int:
    all_ok = True
    if argv:
        items = []
        for p in argv:
            path = Path(p)
            version = path.parent.parent.name.split("-")[0] if path.parent.parent.name else path.parent.name
            items.append((version, path))
    else:
        items = []
        for version, folder, dll_name in VERSIONS:
            items.append((version, BASE / folder / "Display.Driver" / dll_name))
    for version, dll in items:
        if not dll.exists():
            print(f"{version}: MISSING {dll}")
            all_ok = False
            continue
        pe, image_base = load_pe(dll)
        data = dll.read_bytes()
        size = pe.OPTIONAL_HEADER.SizeOfImage
        records = find_table_records(data, image_base, size)
        print(f"=== {version} ===")
        for name, (id_val, groups) in FUNCS.items():
            va = records.get(id_val)
            if va is None:
                print(f"  {name:10s} MISSING ID")
                all_ok = False
                continue
            rva = va - image_base
            try:
                off = pe.get_offset_from_rva(rva)
                insns = disasm_function(data[off:], rva, image_base)
            except Exception as e:
                print(f"  {name:10s} disasm error: {e}")
                all_ok = False
                continue
            ok, missing = group_ok(insns, groups)
            status = "OK" if ok else f"MISSING {missing}"
            if not ok:
                all_ok = False
            print(f"  {name:10s} RVA {rva:#x} {status}")
    print("ALL_OK" if all_ok else "SOME_FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
