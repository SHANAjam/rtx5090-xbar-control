"""Command-line interface for xbar5090."""

from __future__ import annotations

import argparse
import os
import sys

from . import backup as backup_mod
from . import clk_domains, driver_check, prop_rels, safety, vf_points
from . import perf_limits
from .nvapi import NvApi, bytes_to_buf, buf_to_bytes, get_u32, is_admin

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backups")
VF_CTRL_SIZE = vf_points.VF_CTRL_VER


def _api(gpu_index: int = 0) -> NvApi:
    return NvApi(gpu_index=gpu_index)


def _ensure_supported() -> bool:
    ok, msg = driver_check.ensure_supported_driver()
    if not ok:
        print(f"ERROR: {msg}", file=sys.stderr)
        return False
    return True


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
    if not _ensure_supported():
        return 2
    try:
        safety.check_xbar_freq(args.freq_khz)
        safety.check_msvdd(args.msvdd_uv)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
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
    try:
        old_f, old_m, new_f, new_m = clk_domains.write_clock_domains(api, args.freq_khz, args.msvdd_uv)
    except Exception as e:
        clk_domains.restore_from_buf(api, clk_buf)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3
    print(f"XBAR {old_f} -> {new_f} kHz, MSVDD {old_m} -> {new_m} uV")
    if new_f != args.freq_khz or new_m != args.msvdd_uv:
        clk_domains.restore_from_buf(api, clk_buf)
        print("ERROR: readback mismatch, rolled back.", file=sys.stderr)
        return 3
    return 0


def cmd_set_ratio(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: set-ratio requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported():
        return 2
    if args.raw is not None:
        raw = args.raw
        if not (0 <= raw <= 2 * 65536):
            print("ERROR: ratio raw out of range.", file=sys.stderr)
            return 2
    else:
        if not (0.0 <= args.ratio <= 2.0):
            print("ERROR: ratio out of range.", file=sys.stderr)
            return 2
        raw = prop_rels.ratio_float_to_raw(args.ratio)

    prop_buf, old_r = prop_rels.read_prop_rels(api)
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_set_ratio_pre", prop_buf,
                                  {"kind": "prop_rels", "ratio_raw": old_r})
    try:
        _, new_r = prop_rels.write_prop_rels(api, raw)
    except Exception as e:
        prop_rels.restore_from_buf(api, prop_buf)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3
    print(f"Ratio raw {old_r} -> {new_r} ({prop_rels.ratio_raw_to_float(new_r):.6f})")
    if new_r != raw:
        prop_rels.restore_from_buf(api, prop_buf)
        print("ERROR: readback mismatch, rolled back.", file=sys.stderr)
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
    if not _ensure_supported():
        return 2
    try:
        safety.check_xbar_freq(args.freq_khz)
        if not (0 <= args.start <= args.end <= 2047):
            raise ValueError("VF range must satisfy 0 <= start <= end <= 2047")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    active = vf_points.active_mask(api)
    pre = vf_points.get_control(api, active)
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_vfp_set_pre", pre,
                                  {"kind": "vf_control", "start": args.start, "end": args.end,
                                   "freq_khz": args.freq_khz})
    try:
        after = vf_points.set_xbar_range(api, args.start, args.end, args.freq_khz)
    except Exception as e:
        vf_points.set_control(api, pre)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3

    # Readback compare each modified flat.
    bad = []
    for flat in range(args.start, args.end + 1):
        rec = vf_points.CTRL_REC_BASE + flat * vf_points.CTRL_REC_STRIDE
        if get_u32(after, rec) != 0xD:
            continue
        got = _i32(get_u32(after, rec + 0x38))
        if got != args.freq_khz:
            bad.append((flat, got))
    if bad:
        vf_points.set_control(api, pre)
        print(f"ERROR: readback mismatch on flats {bad[:10]}, rolled back.", file=sys.stderr)
        return 3
    print("Readback OK.")
    return 0


def cmd_vfp_restore(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: vfp restore requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported():
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


def cmd_reset(args, api: NvApi) -> int:
    """Reset XBAR/MSVDD/ratio/VF to driver defaults (one command)."""
    if not is_admin():
        print("ERROR: reset requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported():
        return 2

    # Backup current state
    clk_buf, old_f, old_m = clk_domains.read_clock_domains(api)
    prop_buf, old_r = prop_rels.read_prop_rels(api)
    active = vf_points.active_mask(api)
    vf_pre = vf_points.get_control(api, active)
    backup_mod.save_binary_backup(BACKUP_DIR, "reset_clk_pre", clk_buf,
                                  {"kind": "clk_domains", "freq_khz": old_f, "msvdd_uv": old_m})
    backup_mod.save_binary_backup(BACKUP_DIR, "reset_prop_pre", prop_buf,
                                  {"kind": "prop_rels", "ratio_raw": old_r})
    backup_mod.save_binary_backup(BACKUP_DIR, "reset_vf_pre", vf_pre, {"kind": "vf_control"})

    try:
        clk_domains.write_clock_domains(api, 0, 0)
        prop_rels.write_prop_rels(api, prop_rels.DEFAULT_RATIO_RAW)
        bank = vf_points.detect_xbar_bank(api)
        if bank is None:
            raise RuntimeError("cannot detect XBAR bank for reset")
        vf_points.set_xbar_range(api, bank[0], bank[1], 0)
    except Exception as e:
        clk_domains.restore_from_buf(api, clk_buf)
        prop_rels.restore_from_buf(api, prop_buf)
        vf_points.set_control(api, vf_pre)
        print(f"ERROR: reset failed, rolled back: {e}", file=sys.stderr)
        return 3

    print("Reset to driver defaults: XBAR 0, MSVDD 0, ratio 0.9, VF 0.")
    return 0


def cmd_snapshot(args, api: NvApi) -> int:
    clk_buf, _, _ = clk_domains.read_clock_domains(api)
    prop_buf, _ = prop_rels.read_prop_rels(api)
    active = vf_points.active_mask(api)
    vf_buf = vf_points.get_control(api, active)
    path = backup_mod.save_snapshot(BACKUP_DIR, "snapshot", clk_buf, prop_buf, vf_buf,
                                    {"gpu_index": api.gpu_index})
    print(f"Snapshot saved: {path}")
    return 0


def cmd_restore_snapshot(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: restore-snapshot requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported():
        return 2
    snap = backup_mod.load_snapshot(args.snapshot)
    clk_buf = bytes_to_buf(snap["clk_bytes"], clk_domains.CLK_DOMAINS_BUFSIZE)
    prop_buf = bytes_to_buf(snap["prop_bytes"], prop_rels.PROP_RELS_BUFSIZE)
    vf_buf = bytes_to_buf(snap["vf_bytes"], vf_points.VF_CTRL_VER)

    # Back up current state before restore.
    cur_clk, _, _ = clk_domains.read_clock_domains(api)
    cur_prop, _ = prop_rels.read_prop_rels(api)
    cur_vf = vf_points.get_control(api, vf_points.active_mask(api))
    backup_mod.save_snapshot(BACKUP_DIR, "pre_restore", cur_clk, cur_prop, cur_vf,
                             {"gpu_index": api.gpu_index})

    try:
        clk_domains.restore_from_buf(api, clk_buf)
        prop_rels.restore_from_buf(api, prop_buf)
        vf_points.set_control(api, vf_buf)
    except Exception as e:
        clk_domains.restore_from_buf(api, cur_clk)
        prop_rels.restore_from_buf(api, cur_prop)
        vf_points.set_control(api, cur_vf)
        print(f"ERROR: restore failed, rolled back: {e}", file=sys.stderr)
        return 3

    # Verify readback.
    _, f, m = clk_domains.read_clock_domains(api)
    _, r = prop_rels.read_prop_rels(api)
    after_vf = vf_points.get_control(api, vf_points.active_mask(api))
    if bytes(after_vf) != snap["vf_bytes"]:
        print("WARNING: VF readback differs from snapshot.", file=sys.stderr)
        return 3
    print(f"Restored snapshot. XBAR={f} kHz, MSVDD={m} uV, ratio_raw={r}")
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
    if not _ensure_supported():
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

    # Apply with rollback on failure
    try:
        clk_domains.write_clock_domains(api, new_freq, new_msvdd)
        prop_rels.write_prop_rels(api, prop_rels.ratio_float_to_raw(new_ratio))
        vf_points.set_xbar_range(api, new_vf_start, new_vf_end, new_vf_freq)
    except Exception as e:
        clk_domains.restore_from_buf(api, clk_buf)
        prop_rels.restore_from_buf(api, prop_buf)
        vf_points.set_control(api, vf_pre)
        print(f"ERROR: apply failed, rolled back: {e}", file=sys.stderr)
        return 3

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
    parser.add_argument("--gpu", type=int, default=0, help="GPU index (default 0)")
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
    sub.add_parser("reset", help="reset XBAR/MSVDD/ratio/VF to driver defaults").set_defaults(func=cmd_reset)
    sub.add_parser("snapshot", help="save clk+prop+vf snapshot").set_defaults(func=cmd_snapshot)
    p_rs = sub.add_parser("restore-snapshot", help="restore clk+prop+vf snapshot")
    p_rs.add_argument("--snapshot", required=True)
    p_rs.set_defaults(func=cmd_restore_snapshot)

    args = parser.parse_args(argv)
    try:
        api = _api(args.gpu)
    except Exception as e:
        print(f"Failed to init NvAPI: {e}", file=sys.stderr)
        return 2
    return args.func(args, api)


if __name__ == "__main__":
    sys.exit(main())
