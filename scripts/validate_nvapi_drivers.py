#!/usr/bin/env python3
"""Cross-version static validation of private NvAPI PropRels IDs.

For each nvapi64.dll / nvapi64_impl.dll, locate the static ID->VA table for
0xE826E4F0 (GET_INFO), 0xCBFF71D0 (GET_CONTROL), 0xEF3D20EA (SET_CONTROL),
then disassemble the target functions and check for the expected version
constants and GET_INFO record layout markers.

Usage:
    python scripts/validate_nvapi_drivers.py <dll> [<dll> ...]
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import capstone
import pefile

IDS = {
    "GET_INFO": 0xE826E4F0,
    "GET_CONTROL": 0xCBFF71D0,
    "SET_CONTROL": 0xEF3D20EA,
}

EXTRA_IDS = {
    "CLK_GET": 0xF58938F5,
    "CLK_SET": 0xD14B69CF,
    "VF_INFO": 0x8895B510,
    "VF_STATUS": 0x7FEE9032,
    "VF_GET": 0xDA025C3E,
    "VF_SET": 0xFEC00D04,
    "PERF_GET": 0xEFCEDD1F,
}

VERSION_CONSTANTS = {
    "GET_INFO": 0x15798,
    "GET_CONTROL": 0x1075C,
    "SET_CONTROL": 0x1075C,
    "CLK_GET": 0x261A4,
    "VF_INFO": 0x78604,
    "VF_STATUS": 0x1E8604,
    "VF_GET": 0x474604,
    "VF_SET": 0x474604,
}


def load_pe(path: Path):
    pe = pefile.PE(str(path), fast_load=False)
    return pe, pe.OPTIONAL_HEADER.ImageBase


def find_table_records(data: bytes, image_base: int, image_size: int,
                       ids: dict[str, int] | None = None):
    """Return {id: ptr_va} by scanning for 16-byte records.

    Tries both layouts:
      A: ptr(8) id(4) pad(4)
      B: id(4) pad(4) ptr(8)
    """
    if ids is None:
        ids = {**IDS, **EXTRA_IDS}
    found = {}
    for id_val in ids.values():
        key = struct.pack("<I", id_val)
        for off in range(0, len(data) - 16, 4):
            if data[off:off + 4] != key:
                continue
            # Layout A: ptr at off-8
            if off >= 8:
                ptr = struct.unpack_from("<Q", data, off - 8)[0]
                pad = struct.unpack_from("<I", data, off + 4)[0]
                if (image_base <= ptr < image_base + image_size) and pad == 0:
                    found[id_val] = ptr
                    break
            # Layout B: ptr at off+8
            if off + 12 <= len(data):
                ptr = struct.unpack_from("<Q", data, off + 8)[0]
                pad = struct.unpack_from("<I", data, off + 4)[0]
                if (image_base <= ptr < image_base + image_size) and pad == 0:
                    found[id_val] = ptr
                    break
    return found


def disasm_function(data: bytes, rva: int, image_base: int, size: int = 0x800):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    insns = []
    for ins in md.disasm(data, image_base + rva):
        insns.append(ins)
        if ins.mnemonic == "ret" and len(insns) > 8:
            break
        if len(insns) >= 600:
            break
    return insns


def check_version_constant(insns, expected: int) -> bool:
    needle = "0x%x" % expected
    for ins in insns:
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_IMM and op.imm == expected:
                return True
        if needle in ins.op_str:
            return True
    return False


def check_info_layout_markers(insns) -> dict:
    """Look for GET_INFO record write markers: stride 0x150 and base 0x8e8/0x8f0."""
    has_stride_150 = False
    has_base_8e8 = False
    for ins in insns:
        if "0x150" in ins.op_str:
            has_stride_150 = True
        if "0x8e8" in ins.op_str or "0x8f0" in ins.op_str:
            has_base_8e8 = True
    return {"stride_0x150": has_stride_150, "base_0x8e8_or_0x8f0": has_base_8e8}


def validate_one(path: Path) -> dict:
    pe, image_base = load_pe(path)
    data = path.read_bytes()
    image_size = pe.OPTIONAL_HEADER.SizeOfImage
    records = find_table_records(data, image_base, image_size)
    result = {
        "file": str(path),
        "size": len(data),
        "image_base": hex(image_base),
        "records": {},
        "extra_records": {},
        "checks": {},
    }
    for name, id_val in IDS.items():
        ptr_va = records.get(id_val)
        if ptr_va is None:
            result["records"][name] = None
            result["checks"][name] = "ID not found in table"
            continue
        rva = ptr_va - image_base
        result["records"][name] = hex(rva)
        try:
            off = pe.get_offset_from_rva(rva)
        except Exception:
            result["checks"][name] = "RVA not mapped"
            continue
        insns = disasm_function(data[off:], rva, image_base)
        ok_version = check_version_constant(insns, VERSION_CONSTANTS[name])
        info = {}
        if name == "GET_INFO":
            info = check_info_layout_markers(insns)
        result["checks"][name] = {
            "version_ok": ok_version,
            **info,
        }
    result["extra_checks"] = {}
    for name, id_val in EXTRA_IDS.items():
        ptr_va = records.get(id_val)
        result["extra_records"][name] = hex(ptr_va - image_base) if ptr_va else None
        if ptr_va is None:
            result["extra_checks"][name] = "ID not found"
            continue
        rva = ptr_va - image_base
        try:
            off = pe.get_offset_from_rva(rva)
            insns = disasm_function(data[off:], rva, image_base)
        except Exception:
            result["extra_checks"][name] = "disasm failed"
            continue
        expected = VERSION_CONSTANTS.get(name)
        result["extra_checks"][name] = (
            check_version_constant(insns, expected) if expected is not None else "present"
        )
    return result


def main(argv=None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"MISSING {path}")
            continue
        try:
            r = validate_one(path)
            print("=" * 80)
            print(r["file"], f"({r['size']} bytes, image_base={r['image_base']})")
            for name in IDS:
                rec = r["records"].get(name)
                chk = r["checks"].get(name)
                print(f"  {name:12s} -> RVA {rec}")
                if isinstance(chk, dict):
                    print(f"               {chk}")
                else:
                    print(f"               {chk}")
            missing = [k for k, v in r["extra_records"].items() if v is None]
            if missing:
                print(f"  MISSING extra IDs: {', '.join(missing)}")
            else:
                print(f"  extra IDs all present: {', '.join(r['extra_records'])}")
            bad_extra = [k for k, v in r["extra_checks"].items() if v is not True and v != "present"]
            if bad_extra:
                print(f"  extra checks FAILED: {bad_extra} -> { {k: r['extra_checks'][k] for k in bad_extra} }")
            else:
                print(f"  extra version checks all OK")
        except Exception as e:
            print(f"ERROR {path}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
