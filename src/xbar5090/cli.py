"""Command-line interface for xbar5090."""

from __future__ import annotations

import argparse
import os
import sys

from . import backup as backup_mod
from . import clk_domains, prop_rels, vf_points
from . import perf_limits
from .nvapi import NvApi, bytes_to_buf, buf_to_bytes, get_u32, is_admin

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backups")
VF_CTRL_SIZE = vf_points.VF_CTRL_VER


def _api() -> NvApi:
    return NvApi()


def cmd_status(args, api: NvApi) -> int:
    _, freq, msvdd = clk_domains.read_clock_domains(api)
    _, raw = prop_rels.read_prop_rels(api)
    ratio = prop_rels.ratio_raw_to_float(raw)
    print(f"XBAR offset  : {freq/1000:+.0f} MHz")
    print(f"MSVDD offset : {msvdd/1000:+.1f} mV")
    print(f"Ratio        : {ratio:.4f}")
    return 0


def cmd_set_xbar(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: set-xbar requires administrator.", file=sys.stderr)
        return 2
    _, old_f, old_m = clk_domains.read_clock_domains(api)
    _, old_r = prop_rels.read_prop_rels(api)
    # backup
    clk_buf, _, _ = clk_domains.read_clock_domains(api)
    prop_buf, _ = prop_rels.read_prop_rels(api)
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_set_xbar_pre", clk_buf,
                                  {"kind": "clk_domains", "freq_khz": old_f, "msvdd_uv": old_m})
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_set_xbar_pre", prop_buf,
                                  {"kind": "prop_rels", "ratio_raw": old_r})
    old_f, old_m, new_f, new_m = clk_domains.write_clock_domains(api, args.freq_khz, args.msvdd_uv)
    print(f"XBAR {old_f} -> {new_f} kHz, MSVDD {old_m} -> {new_m} uV")
    if new_f != args.freq_khz or new_m != args.msvdd_uv:
        print("WARNING: readback mismatch!", file=sys.stderr)
        return 3
    return 0


def cmd_set_ratio(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: set-ratio requires administrator.", file=sys.stderr)
        return 2
    if args.raw is not None:
        raw = args.raw
    else:
        raw = prop_rels.ratio_float_to_raw(args.ratio)
    _, old_r = prop_rels.read_prop_rels(api)
    _, new_r = prop_rels.write_prop_rels(api, raw)
    print(f"Ratio raw {old_r} -> {new_r} ({prop_rels.ratio_raw_to_float(new_r):.6f})")
    if new_r != raw:
        print("WARNING: readback mismatch!", file=sys.stderr)
        return 3
    return 0


def cmd_vfp_status(args, api: NvApi) -> int:
    active = vf_points.active_mask(api)
    bank = vf_points.detect_xbar_bank(api)
    if bank is None:
        print("WARNING: could not auto-detect XBAR V/F bank; showing validated default 127..253.",
              file=sys.stderr)
        start, end = vf_points.XBAR_START, vf_points.XBAR_END
    else:
        start, end = bank
    buf = vf_points.get_status(api, active)
    print(f"Active flats: {len(active)}")
    print(f"Detected XBAR bank: {start}..{end}")
    for i in range(start, end + 1):
        r = vf_points.decode_status_record(buf, i)
        print(f"{r['flat']:4d} type={r['type']:#x} base={r['base_freq_mhz']} MHz "
              f"volt={r['voltage_uv']} uV off={r['total_freq_offset_khz']} kHz "
              f"eff={r['effective_freq_mhz']} MHz")
    return 0


def cmd_vfp_set_range(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: vfp set-range requires administrator.", file=sys.stderr)
        return 2
    active = vf_points.active_mask(api)
    pre = vf_points.get_control(api, active)
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_vfp_set_pre", pre,
                                  {"kind": "vf_control", "start": args.start, "end": args.end,
                                   "freq_khz": args.freq_khz})
    after = vf_points.set_xbar_range(api, args.start, args.end, args.freq_khz)
    print("Readback OK.")
    return 0


def cmd_vfp_restore(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: vfp restore requires administrator.", file=sys.stderr)
        return 2
    buf = backup_mod.load_binary_backup(args.backup, VF_CTRL_SIZE)
    vf_points.set_control(api, buf)
    active = vf_points.active_mask(api)
    after = vf_points.get_control(api, active)
    if buf_to_bytes(after) != buf_to_bytes(buf):
        print("RESTORE FAIL: readback mismatch", file=sys.stderr)
        return 3
    print("RESTORE PASS")
    return 0


def cmd_perf(args, api: NvApi) -> int:
    buf = perf_limits.get_perf_limits(api)
    for uid in (perf_limits.XBAR_MAX_USER_ID, perf_limits.XBAR_MIN_USER_ID):
        base = perf_limits.find_entry_by_user_id(buf, uid)
        if base is None:
            print(f"user_id {uid:#x}: not found")
            continue
        vals = [get_u32(buf, base + o) for o in range(0, 0x40, 4)]
        print(f"user_id {uid:#x} base={base:#x} first8={[hex(v) for v in vals[:8]]}")
    return 0


def _i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v if v < 0x80000000 else v - 0x100000000


def _prompt_int(label: str, current: int, lo: int, hi: int, unit: str = "") -> int:
    while True:
        inp = input(f"{label} [{lo}..{hi}] (current {current}{unit}, Enter=keep): ").strip()
        if not inp:
            return current
        try:
            v = int(inp)
        except ValueError:
            print("  Invalid number.")
            continue
        if lo <= v <= hi:
            return v
        print(f"  Must be between {lo} and {hi}.")


def _prompt_float(label: str, current: float, lo: float, hi: float) -> float:
    while True:
        inp = input(f"{label} [{lo}..{hi}] (current {current:.6f}, Enter=keep): ").strip()
        if not inp:
            return current
        try:
            v = float(inp)
        except ValueError:
            print("  Invalid number.")
            continue
        if lo <= v <= hi:
            return v
        print(f"  Must be between {lo} and {hi}.")


def cmd_wizard(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: wizard writes require administrator.", file=sys.stderr)
        return 2

    # Current values
    _, freq, msvdd = clk_domains.read_clock_domains(api)
    _, raw = prop_rels.read_prop_rels(api)
    ratio = prop_rels.ratio_raw_to_float(raw)

    active = vf_points.active_mask(api)
    bank = vf_points.detect_xbar_bank(api)
    if bank is None:
        print("ERROR: could not auto-detect the XBAR V/F bank on this GPU/driver.", file=sys.stderr)
        print("Refusing to continue. This project may not support this environment.", file=sys.stderr)
        return 2
    bank_start, bank_end = bank
    status_buf = vf_points.get_status(api, active)

    # Ask for the current physical MSVDD (mV), then pick a broad VF range
    # around the closest V/F point.
    current_msvdd_mv = _prompt_float(
        "Current physical MSVDD (mV)", 1150.0, 500.0, 1500.0)
    closest = bank_start
    best_diff = float("inf")
    for i in range(bank_start, bank_end + 1):
        rec = vf_points.decode_status_record(status_buf, i)
        diff = abs(rec["voltage_uv"] - current_msvdd_mv * 1000)
        if diff < best_diff:
            best_diff = diff
            closest = i

    default_start = max(bank_start, closest - 15)
    default_end = min(bank_end, closest + 15)

    ctrl = vf_points.get_control(api, active)
    sample_flat = (default_start + default_end) // 2
    vf_rec = vf_points.CTRL_REC_BASE + sample_flat * vf_points.CTRL_REC_STRIDE
    cur_vf = _i32(get_u32(ctrl, vf_rec + 0x38)) if get_u32(ctrl, vf_rec) == 0xD else 0

    print("=== xbar5090 interactive setup ===")
    print(f"Detected XBAR V/F bank on this machine: {bank_start}..{bank_end}")
    print(f"Current XBAR offset : {freq/1000:+.0f} MHz")
    print(f"Current MSVDD offset: {msvdd/1000:+.1f} mV")
    print(f"Current ratio       : {ratio:.4f}")
    print(f"Input MSVDD         : {current_msvdd_mv:.0f} mV")
    print(f"MSVDD-based VF range: {default_start}..{default_end}")
    print(f"Current VF offset (flat {sample_flat}): {cur_vf/1000:+.0f} MHz")

    new_freq_mhz = _prompt_float("XBAR offset (MHz)", freq / 1000, -1000.0, 1000.0)
    new_freq = int(round(new_freq_mhz * 1000))
    new_msvdd_mv = _prompt_float("MSVDD offset (mV)", msvdd / 1000, -100.0, 100.0)
    new_msvdd = int(round(new_msvdd_mv * 1000))
    new_ratio = _prompt_float("Propagation ratio", ratio, 0.0, 2.0)
    new_vf_start = _prompt_int(
        f"VF bank start index (detected {bank_start}..{bank_end})",
        default_start, bank_start, bank_end)
    new_vf_end = _prompt_int(
        f"VF bank end index (detected {bank_start}..{bank_end})",
        default_end, new_vf_start, bank_end)
    new_vf_freq_mhz = _prompt_float("VF offset (MHz)", cur_vf / 1000, -1000.0, 1000.0)
    new_vf_freq = int(round(new_vf_freq_mhz * 1000))

    print("\n=== Summary ===")
    print(f"XBAR offset : {new_freq/1000:+.0f} MHz")
    print(f"MSVDD offset: {new_msvdd/1000:+.1f} mV")
    print(f"Ratio       : {new_ratio:.4f}")
    print(f"VF range    : {new_vf_start}..{new_vf_end} at {new_vf_freq/1000:+.0f} MHz")
    ans = input("Apply? [y/N] ").strip().lower()
    if ans not in ("y", "yes"):
        print("Cancelled.")
        return 1

    # Backups
    clk_buf, _, _ = clk_domains.read_clock_domains(api)
    prop_buf, _ = prop_rels.read_prop_rels(api)
    vf_pre = vf_points.get_control(api, active)
    backup_mod.save_binary_backup(BACKUP_DIR, "wizard_clk_pre", clk_buf, {"kind": "clk_domains"})
    backup_mod.save_binary_backup(BACKUP_DIR, "wizard_prop_pre", prop_buf, {"kind": "prop_rels"})
    backup_mod.save_binary_backup(BACKUP_DIR, "wizard_vf_pre", vf_pre, {"kind": "vf_control"})

    # Apply
    clk_domains.write_clock_domains(api, new_freq, new_msvdd)
    prop_rels.write_prop_rels(api, prop_rels.ratio_float_to_raw(new_ratio))
    vf_points.set_xbar_range(api, new_vf_start, new_vf_end, new_vf_freq)

    print("Applied.")
    return 0


def cmd_doctor(args, api: NvApi) -> int:
    print("NvAPI initialized OK")
    print("Admin:", is_admin())
    for name, fid in [
        ("ClkDomainsGet", clk_domains.CLK_DOMAINS_GET_CONTROL),
        ("ClkDomainsSet", clk_domains.CLK_DOMAINS_SET_CONTROL),
        ("PropRelsGet", prop_rels.PROP_RELS_GET_CONTROL),
        ("PropRelsSet", prop_rels.PROP_RELS_SET_CONTROL),
        ("VF_INFO", vf_points.VF_INFO),
        ("VF_STATUS", vf_points.VF_STATUS),
        ("VF_GET_CONTROL", vf_points.VF_GET_CONTROL),
        ("VF_SET_CONTROL", vf_points.VF_SET_CONTROL),
        ("PERF_GET", perf_limits.PERF_GET),
    ]:
        try:
            api._fn(fid)
            print(f"{name:16s} {fid:#010x} OK")
        except Exception as e:
            print(f"{name:16s} {fid:#010x} FAIL: {e}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="xbar5090", description="RTX 5090 XBAR controls via private NvAPI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)
    p_x = sub.add_parser("set-xbar")
    p_x.add_argument("--freq-khz", type=int, required=True)
    p_x.add_argument("--msvdd-uv", type=int, default=0)
    p_x.set_defaults(func=cmd_set_xbar)
    p_r = sub.add_parser("set-ratio")
    p_r.add_argument("--ratio", type=float)
    p_r.add_argument("--raw", type=lambda x: int(x, 0))
    p_r.set_defaults(func=cmd_set_ratio)
    sub.add_parser("vfp-status").set_defaults(func=cmd_vfp_status)
    p_vr = sub.add_parser("vfp-set-range")
    p_vr.add_argument("--start", type=int, required=True)
    p_vr.add_argument("--end", type=int, required=True)
    p_vr.add_argument("--freq-khz", type=int, required=True)
    p_vr.set_defaults(func=cmd_vfp_set_range)
    p_rest = sub.add_parser("vfp-restore")
    p_rest.add_argument("--backup", required=True)
    p_rest.set_defaults(func=cmd_vfp_restore)
    sub.add_parser("perf").set_defaults(func=cmd_perf)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("wizard", help="interactive setup with ranges and current values").set_defaults(func=cmd_wizard)

    args = parser.parse_args(argv)
    try:
        api = _api()
    except Exception as e:
        print(f"Failed to init NvAPI: {e}", file=sys.stderr)
        return 2
    return args.func(args, api)


if __name__ == "__main__":
    sys.exit(main())
