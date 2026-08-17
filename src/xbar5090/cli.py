"""Command-line interface for xbar5090."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import subprocess
import sys
import time

from . import backup as backup_mod
from . import clk_domains, driver_check, prop_rels, safety, vf_points
from . import perf_limits
from . import probe
from . import crack
from . import l2test
from .nvapi import NvApi, bytes_to_buf, buf_to_bytes, get_u32, i32, is_admin

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKUP_DIR = os.path.join(APP_DIR, "backups")
PROFILES_DIR = os.path.join(APP_DIR, "profiles")
VF_CTRL_SIZE = vf_points.VF_CTRL_VER


def _api(gpu_index: int = 0) -> NvApi:
    return NvApi(gpu_index=gpu_index)


def _ensure_supported_auto(api: NvApi, args) -> bool:
    """Like _ensure_supported, but automatically tries crack for unknown drivers."""
    if getattr(args, "force_driver", False):
        print("WARNING: --force-driver set, skipping driver/GPU checks.", file=sys.stderr)
        return True
    ok, msg = driver_check.ensure_supported_driver()
    if ok:
        ok_gpu, msg_gpu = driver_check.ensure_supported_gpu()
        if not ok_gpu:
            print(f"ERROR: {msg_gpu}", file=sys.stderr)
            return False
        return True
    # Driver not in known list: auto-verify with crack -> probe -> status.
    print("Driver not in known list. Running auto-crack...", file=sys.stderr)
    candidates_path = os.path.join(APP_DIR, "candidates.json")
    try:
        if not crack.crack_driver(api, candidates_path=candidates_path):
            print(f"ERROR: {msg}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"ERROR: auto-crack failed: {e}", file=sys.stderr)
        return False
    ok2, msg2 = driver_check.ensure_supported_driver()
    if not ok2:
        print(f"ERROR: {msg2}", file=sys.stderr)
        return False
    ok_gpu, msg_gpu = driver_check.ensure_supported_gpu()
    if not ok_gpu:
        print(f"ERROR: {msg_gpu}", file=sys.stderr)
        return False
    # Now run probe (read-only) to confirm the full layout is still valid.
    if not probe.probe_driver(api):
        # Gentle mode: crack passed but probe failed. This may be a false
        # negative on a different VBIOS, so ask the user before refusing.
        print("WARNING: probe failed after crack. This may be a false negative.", file=sys.stderr)
        if getattr(args, "yes", False):
            print("  --yes specified, continuing despite probe failure.", file=sys.stderr)
        else:
            ans = input("Type 'yes' to continue despite probe failure: ").strip().lower()
            if ans not in ("yes", "y"):
                print("Cancelled.", file=sys.stderr)
                return False
    # Show current status so the user sees what is being read.
    try:
        cmd_status(args, api)
    except Exception as e:
        print(f"WARNING: status display failed: {e}", file=sys.stderr)
    return True


def _confirm_step(args, label: str, delta, limit, unit: str = "kHz") -> bool:
    """Return True if the step is allowed. Warns/prompts when the step is large."""
    if abs(delta) <= limit:
        return True
    print(f"WARNING: {label} step {delta:+d} {unit} exceeds safety limit {limit} {unit}.",
          file=sys.stderr)
    if getattr(args, "yes", False):
        print("  --yes specified, continuing.", file=sys.stderr)
        return True
    ans = input(f"Type 'yes' to continue with this large step: ").strip().lower()
    return ans in ("yes", "y")


def _confirm_validated(args, label: str, is_ok: bool, detail: str) -> bool:
    """Warn when a value is outside the validated range; ask for confirmation."""
    if is_ok:
        return True
    print(f"WARNING: {label} is outside the validated range: {detail}", file=sys.stderr)
    if getattr(args, "yes", False):
        print("  --yes specified, continuing.", file=sys.stderr)
        return True
    ans = input(f"Type 'yes' to continue with this unvalidated value: ").strip().lower()
    return ans in ("yes", "y")


def _safe_restore(restore_func, label: str, original_exc: Exception | None = None) -> None:
    """Run a rollback and report if the rollback itself fails."""
    try:
        restore_func()
    except Exception as rollback_exc:
        if original_exc is not None:
            print(f"ERROR: original failure: {original_exc}", file=sys.stderr)
        print(f"ERROR: rollback of {label} failed: {rollback_exc}", file=sys.stderr)


_last_write_time = 0.0
WRITE_COOLDOWN_SECONDS = 1.0
LOG = logging.getLogger("xbar5090")


def _setup_logging(args) -> None:
    level = logging.WARNING
    if getattr(args, "verbose", False):
        level = logging.DEBUG
    elif getattr(args, "quiet", False):
        level = logging.ERROR
    handlers = [logging.StreamHandler()]
    log_file = getattr(args, "log_file", None)
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s")


def _write_cooldown() -> None:
    """Enforce a short delay between write commands to protect the driver."""
    global _last_write_time
    elapsed = time.monotonic() - _last_write_time
    if elapsed < WRITE_COOLDOWN_SECONDS:
        time.sleep(WRITE_COOLDOWN_SECONDS - elapsed)
    _last_write_time = time.monotonic()


def _ctrl_rec(flat: int) -> int:
    """Return the CONTROL record offset for a flat using the discovered layout."""
    rec_base, rec_stride = vf_points.control_layout()
    return rec_base + flat * rec_stride


def cmd_status(args, api: NvApi) -> int:
    _, freq, msvdd = clk_domains.read_clock_domains(api)
    _, raw = prop_rels.read_prop_rels(api)
    ratio = prop_rels.ratio_raw_to_float(raw)
    phys = None
    try:
        phys = clk_domains.measure_xbar_khz(api)
    except Exception as e:
        if not getattr(args, "json", False):
            print(f"Physical XBAR: unavailable ({e})", file=sys.stderr)
    if getattr(args, "json", False):
        print(json.dumps({
            "xbar_offset_khz": freq,
            "msvdd_offset_uv": msvdd,
            "ratio": ratio,
            "physical_xbar_khz": phys,
        }, indent=2))
        return 0
    print(f"XBAR offset  : {freq/1000:+.0f} MHz")
    print(f"MSVDD offset : {msvdd/1000:+.1f} mV")
    print(f"Ratio        : {ratio:.4f}")
    if phys is not None:
        print(f"Physical XBAR: {phys/1000:.0f} MHz")
    return 0


def cmd_set_xbar(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: set-xbar requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported_auto(api, args):
        return 2
    try:
        safety.check_xbar_freq(args.freq_khz)
        safety.check_msvdd(args.msvdd_uv)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    clk_buf, old_f, old_m = clk_domains.read_clock_domains(api)
    prop_buf, old_r = prop_rels.read_prop_rels(api)

    if not _confirm_step(args, "XBAR", args.freq_khz - old_f, safety.MAX_XBAR_STEP_KHZ):
        print("Cancelled.", file=sys.stderr)
        return 1
    if not _confirm_step(args, "MSVDD", args.msvdd_uv - old_m, safety.MAX_MSVDD_STEP_UV, "uV"):
        print("Cancelled.", file=sys.stderr)
        return 1
    if not _confirm_validated(args, "XBAR offset",
                              safety.is_validated_xbar(args.freq_khz),
                              f"{args.freq_khz} kHz"):
        print("Cancelled.", file=sys.stderr)
        return 1
    if not _confirm_validated(args, "MSVDD offset",
                              safety.is_validated_msvdd(args.msvdd_uv),
                              f"{args.msvdd_uv} uV"):
        print("Cancelled.", file=sys.stderr)
        return 1

    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_set_xbar_pre", clk_buf,
                                  {"kind": "clk_domains", "freq_khz": old_f, "msvdd_uv": old_m,
                                   "gpu_index": api.gpu_index})
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_set_xbar_pre", prop_buf,
                                  {"kind": "prop_rels", "ratio_raw": old_r,
                                   "gpu_index": api.gpu_index})
    try:
        old_f, old_m, new_f, new_m = clk_domains.write_clock_domains(api, args.freq_khz, args.msvdd_uv)
    except Exception as e:
        _safe_restore(lambda: clk_domains.restore_from_buf(api, clk_buf), "clk_domains", e)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3
    print(f"XBAR {old_f} -> {new_f} kHz, MSVDD {old_m} -> {new_m} uV")
    if new_f != args.freq_khz or new_m != args.msvdd_uv:
        _safe_restore(lambda: clk_domains.restore_from_buf(api, clk_buf), "clk_domains", None)
        print("ERROR: readback mismatch, rolled back.", file=sys.stderr)
        return 3
    try:
        phys = clk_domains.measure_xbar_khz(api)
        print(f"Physical XBAR now: {phys/1000:.0f} MHz")
    except Exception as e:
        print(f"WARNING: could not measure physical XBAR: {e}", file=sys.stderr)
    return 0


def cmd_set_ratio(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: set-ratio requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported_auto(api, args):
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

    if not _confirm_validated(args, "Ratio",
                              safety.is_validated_ratio(prop_rels.ratio_raw_to_float(raw)),
                              f"{prop_rels.ratio_raw_to_float(raw):.4f}"):
        print("Cancelled.", file=sys.stderr)
        return 1

    if not getattr(args, "force_driver", False) and not prop_rels.validate_prop_rels(api):
        print("ERROR: PropRels GET_INFO/GET_CONTROL validation failed; refusing to write ratio.", file=sys.stderr)
        return 2

    prop_buf, old_r = prop_rels.read_prop_rels(api)
    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_set_ratio_pre", prop_buf,
                                  {"kind": "prop_rels", "ratio_raw": old_r,
                                   "gpu_index": api.gpu_index})
    try:
        _, new_r = prop_rels.write_prop_rels(api, raw)
    except Exception as e:
        _safe_restore(lambda: prop_rels.restore_from_buf(api, prop_buf), "prop_rels", e)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3
    print(f"Ratio raw {old_r} -> {new_r} ({prop_rels.ratio_raw_to_float(new_r):.6f})")
    if new_r != raw:
        _safe_restore(lambda: prop_rels.restore_from_buf(api, prop_buf), "prop_rels", None)
        print("ERROR: readback mismatch, rolled back.", file=sys.stderr)
        return 3
    return 0


def cmd_vfp_status(args, api: NvApi) -> int:
    active = vf_points.active_mask(api)
    bank = vf_points.detect_xbar_bank(api)
    if bank is None:
        if not getattr(args, "json", False):
            print("WARNING: could not auto-detect XBAR V/F bank; no bank available.",
                  file=sys.stderr)
        start, end = 0, -1
    else:
        start, end = bank
    buf = vf_points.get_status(api, active)
    records = []
    for i in range(start, end + 1):
        r = vf_points.decode_status_record(buf, i)
        records.append(r)
    if getattr(args, "json", False):
        print(json.dumps({
            "active_flats": len(active),
            "xbar_bank_start": start,
            "xbar_bank_end": end,
            "records": records,
        }, indent=2))
        return 0
    print(f"Active flats: {len(active)}")
    print(f"Detected XBAR bank: {start}..{end}")
    for r in records:
        print(f"{r['flat']:4d} type={r['type']:#x} base={r['base_freq_mhz']} MHz "
              f"volt={r['voltage_uv']} uV off={r['total_freq_offset_khz']} kHz "
              f"eff={r['effective_freq_mhz']} MHz")
    return 0


def cmd_vfp_set_range(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: vfp set-range requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported_auto(api, args):
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
    # Pre-validate every flat is an XBAR record before any write/backup.
    for flat in range(args.start, args.end + 1):
        if get_u32(pre, _ctrl_rec(flat)) != 0xD:
            print(f"ERROR: flat {flat} is not XBAR type 0xD; refusing to write.", file=sys.stderr)
            return 2
    # Step protection: if any flat changes by more than the VF step limit, ask.
    max_delta = 0
    for flat in range(args.start, args.end + 1):
        rec = _ctrl_rec(flat)
        if get_u32(pre, rec) == 0xD:
            old = i32(get_u32(pre, rec + 0x38))
            max_delta = max(max_delta, abs(args.freq_khz - old))
    if not _confirm_step(args, "VF", max_delta, safety.MAX_VF_STEP_KHZ):
        print("Cancelled.", file=sys.stderr)
        return 1
    if not _confirm_validated(args, "VF offset", args.freq_khz == 88000,
                              f"{args.freq_khz} kHz"):
        print("Cancelled.", file=sys.stderr)
        return 1

    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_vfp_set_pre", pre,
                                  {"kind": "vf_control", "start": args.start, "end": args.end,
                                   "freq_khz": args.freq_khz, "gpu_index": api.gpu_index})
    try:
        after = vf_points.set_xbar_range(api, args.start, args.end, args.freq_khz)
    except Exception as e:
        _safe_restore(lambda: vf_points.set_control(api, pre), "vf_control", e)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3

    # Readback compare each modified flat.
    bad = []
    for flat in range(args.start, args.end + 1):
        rec = _ctrl_rec(flat)
        if get_u32(after, rec) != 0xD:
            continue
        got = i32(get_u32(after, rec + 0x38))
        if got != args.freq_khz:
            bad.append((flat, got))
    if bad:
        _safe_restore(lambda: vf_points.set_control(api, pre), "vf_control", None)
        print(f"ERROR: readback mismatch on flats {bad[:10]}, rolled back.", file=sys.stderr)
        return 3
    print("Readback OK.")
    return 0


def cmd_vfp_auto_range(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: vfp auto-range requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported_auto(api, args):
        return 2

    active = vf_points.active_mask(api)
    bank = vf_points.detect_xbar_bank(api)
    if bank is None:
        print("ERROR: could not auto-detect the XBAR V/F bank on this GPU/driver.", file=sys.stderr)
        return 2
    bank_start, bank_end = bank

    if args.msvdd_mv is None:
        current_msvdd_mv = _prompt_float(
            "Current physical MSVDD (mV)", 1150.0, 500.0, 1500.0)
    else:
        current_msvdd_mv = float(args.msvdd_mv)

    status_buf = vf_points.get_status(api, active)
    closest = bank_start
    best_diff = float("inf")
    for i in range(bank_start, bank_end + 1):
        rec = vf_points.decode_status_record(status_buf, i)
        diff = abs(rec["voltage_uv"] - current_msvdd_mv * 1000)
        if diff < best_diff:
            best_diff = diff
            closest = i

    width = args.width if args.width is not None else 15
    start = max(bank_start, closest - width)
    end = min(bank_end, closest + width)

    print(f"Detected XBAR bank: {bank_start}..{bank_end}")
    print(f"Input MSVDD       : {current_msvdd_mv:.0f} mV")
    print(f"Closest VF point : {closest}")
    print(f"Auto wide range  : {start}..{end} at {args.freq_khz} kHz")

    pre = vf_points.get_control(api, active)
    for flat in range(start, end + 1):
        if get_u32(pre, _ctrl_rec(flat)) != 0xD:
            print(f"ERROR: flat {flat} is not XBAR type 0xD; refusing to write.", file=sys.stderr)
            return 2
    max_delta = 0
    for flat in range(start, end + 1):
        rec = _ctrl_rec(flat)
        if get_u32(pre, rec) == 0xD:
            old = i32(get_u32(pre, rec + 0x38))
            max_delta = max(max_delta, abs(args.freq_khz - old))
    if not _confirm_step(args, "VF", max_delta, safety.MAX_VF_STEP_KHZ):
        print("Cancelled.", file=sys.stderr)
        return 1
    if not _confirm_validated(args, "VF offset", args.freq_khz == 88000,
                              f"{args.freq_khz} kHz"):
        print("Cancelled.", file=sys.stderr)
        return 1

    backup_mod.save_binary_backup(BACKUP_DIR, "xbar5090_vfp_auto_pre", pre,
                                  {"kind": "vf_control", "start": start, "end": end,
                                   "freq_khz": args.freq_khz, "msvdd_mv": current_msvdd_mv,
                                   "gpu_index": api.gpu_index})
    try:
        after = vf_points.set_xbar_range(api, start, end, args.freq_khz)
    except Exception as e:
        _safe_restore(lambda: vf_points.set_control(api, pre), "vf_control", e)
        print(f"ERROR: write failed, rolled back: {e}", file=sys.stderr)
        return 3

    bad = []
    for flat in range(start, end + 1):
        rec = _ctrl_rec(flat)
        if get_u32(after, rec) != 0xD:
            continue
        got = i32(get_u32(after, rec + 0x38))
        if got != args.freq_khz:
            bad.append((flat, got))
    if bad:
        _safe_restore(lambda: vf_points.set_control(api, pre), "vf_control", None)
        print(f"ERROR: readback mismatch on flats {bad[:10]}, rolled back.", file=sys.stderr)
        return 3
    print("Readback OK.")
    return 0


def cmd_vfp_restore(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: vfp restore requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported_auto(api, args):
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
    if not _ensure_supported_auto(api, args):
        return 2

    # Backup current state
    clk_buf, old_f, old_m = clk_domains.read_clock_domains(api)
    prop_buf, old_r = prop_rels.read_prop_rels(api)
    active = vf_points.active_mask(api)
    vf_pre = vf_points.get_control(api, active)
    backup_mod.save_binary_backup(BACKUP_DIR, "reset_clk_pre", clk_buf,
                                  {"kind": "clk_domains", "freq_khz": old_f, "msvdd_uv": old_m,
                                   "gpu_index": api.gpu_index})
    backup_mod.save_binary_backup(BACKUP_DIR, "reset_prop_pre", prop_buf,
                                  {"kind": "prop_rels", "ratio_raw": old_r,
                                   "gpu_index": api.gpu_index})
    backup_mod.save_binary_backup(BACKUP_DIR, "reset_vf_pre", vf_pre,
                                  {"kind": "vf_control", "gpu_index": api.gpu_index})

    try:
        clk_domains.write_clock_domains(api, 0, 0)
        prop_rels.write_prop_rels(api, prop_rels.DEFAULT_RATIO_RAW)
        bank = vf_points.detect_xbar_bank(api)
        if bank is None:
            raise RuntimeError("cannot detect XBAR bank for reset")
        vf_points.set_xbar_range(api, bank[0], bank[1], 0)
    except Exception as e:
        _safe_restore(lambda: clk_domains.restore_from_buf(api, clk_buf), "clk_domains", e)
        _safe_restore(lambda: prop_rels.restore_from_buf(api, prop_buf), "prop_rels", e)
        _safe_restore(lambda: vf_points.set_control(api, vf_pre), "vf_control", e)
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
    if not _ensure_supported_auto(api, args):
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
        _safe_restore(lambda: clk_domains.restore_from_buf(api, cur_clk), "clk_domains", e)
        _safe_restore(lambda: prop_rels.restore_from_buf(api, cur_prop), "prop_rels", e)
        _safe_restore(lambda: vf_points.set_control(api, cur_vf), "vf_control", e)
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


def _profile_path(name: str) -> str:
    return os.path.join(PROFILES_DIR, f"{name}.json")


def cmd_profile_save(args, api: NvApi) -> int:
    name = args.name
    clk_buf, _, _ = clk_domains.read_clock_domains(api)
    prop_buf, _ = prop_rels.read_prop_rels(api)
    active = vf_points.active_mask(api)
    vf_buf = vf_points.get_control(api, active)
    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = _profile_path(name)
    payload = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "clk_b64": base64.b64encode(buf_to_bytes(clk_buf)).decode(),
        "prop_b64": base64.b64encode(buf_to_bytes(prop_buf)).decode(),
        "vf_b64": base64.b64encode(buf_to_bytes(vf_buf)).decode(),
        "gpu_index": api.gpu_index,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Profile saved: {path}")
    return 0


def cmd_profile_apply(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: profile apply requires administrator.", file=sys.stderr)
        return 2
    if not _ensure_supported_auto(api, args):
        return 2
    path = _profile_path(args.name)
    if not os.path.isfile(path):
        print(f"ERROR: profile not found: {path}", file=sys.stderr)
        return 2
    snap = backup_mod.load_snapshot(path)
    clk_buf = bytes_to_buf(snap["clk_bytes"], clk_domains.CLK_DOMAINS_BUFSIZE)
    prop_buf = bytes_to_buf(snap["prop_bytes"], prop_rels.PROP_RELS_BUFSIZE)
    vf_buf = bytes_to_buf(snap["vf_bytes"], vf_points.VF_CTRL_VER)

    cur_clk, _, _ = clk_domains.read_clock_domains(api)
    cur_prop, _ = prop_rels.read_prop_rels(api)
    cur_vf = vf_points.get_control(api, vf_points.active_mask(api))
    backup_mod.save_snapshot(BACKUP_DIR, "pre_profile_apply", cur_clk, cur_prop, cur_vf,
                             {"gpu_index": api.gpu_index})

    try:
        clk_domains.restore_from_buf(api, clk_buf)
        prop_rels.restore_from_buf(api, prop_buf)
        vf_points.set_control(api, vf_buf)
    except Exception as e:
        _safe_restore(lambda: clk_domains.restore_from_buf(api, cur_clk), "clk_domains", e)
        _safe_restore(lambda: prop_rels.restore_from_buf(api, cur_prop), "prop_rels", e)
        _safe_restore(lambda: vf_points.set_control(api, cur_vf), "vf_control", e)
        print(f"ERROR: profile apply failed, rolled back: {e}", file=sys.stderr)
        return 3

    _, f, m = clk_domains.read_clock_domains(api)
    _, r = prop_rels.read_prop_rels(api)
    print(f"Profile applied: {args.name} (XBAR={f} kHz, MSVDD={m} uV, ratio_raw={r})")
    return 0


def cmd_profile_list(args, api: NvApi) -> int:
    if not os.path.isdir(PROFILES_DIR):
        print("No profiles saved.")
        return 0
    for name in sorted(os.listdir(PROFILES_DIR)):
        if name.endswith(".json"):
            print(name[:-5])
    return 0


def cmd_perf(args, api: NvApi) -> int:
    buf = perf_limits.get_perf_limits(api)
    entries = perf_limits.parse_entries(buf)
    if getattr(args, "json", False):
        print(json.dumps({"entries": entries}, indent=2))
        return 0
    for e in entries:
        print(f"user_id {e['user_id']:#x} base={e['base']:#x} first8={[hex(v) for v in e['values'][:8]]}")
    return 0


def _autostart_script_path() -> str:
    return os.path.join(APP_DIR, "autostart_xbar.ps1")


def _write_autostart_script() -> str:
    if getattr(sys, "frozen", False):
        cmd = f"& '{sys.executable}'"
    else:
        py = sys.executable
        run = os.path.join(APP_DIR, "run.py")
        cmd = f"& '{py}' '{run}'"
    script = f"""$ErrorActionPreference = 'Continue'
{cmd} vfp-auto-range --msvdd-mv 1150 --freq-khz 88000 --yes *> $env:TEMP\\xbar5090_autostart.log 2>&1
{cmd} set-xbar --freq-khz 205000 --msvdd-uv 10000 --yes *>> $env:TEMP\\xbar5090_autostart.log 2>&1
{cmd} set-ratio --ratio 1.2 --yes *>> $env:TEMP\\xbar5090_autostart.log 2>&1
"""
    path = _autostart_script_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    return path


def cmd_autostart_install(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: autostart-install requires administrator.", file=sys.stderr)
        return 2
    script = _write_autostart_script()
    task_name = "xbar5090 Autostart"
    cmd = (
        f'schtasks /Create /TN "{task_name}" '
        f'/TR "powershell -NoProfile -ExecutionPolicy Bypass -File \\"{script}\\"" '
        f'/SC ONLOGON /RL HIGHEST /F'
    )
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: failed to create scheduled task: {r.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"Autostart installed: {task_name}")
    print(f"Script: {script}")
    return 0


def cmd_autostart_remove(args, api: NvApi) -> int:
    if not is_admin():
        print("ERROR: autostart-remove requires administrator.", file=sys.stderr)
        return 2
    task_name = "xbar5090 Autostart"
    r = subprocess.run(f'schtasks /Delete /TN "{task_name}" /F', shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: failed to remove scheduled task: {r.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"Autostart removed: {task_name}")
    return 0


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
    if not _ensure_supported_auto(api, args):
        print("Auto-check did not fully pass.", file=sys.stderr)
        ans = input("Continue anyway in risky force mode? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Cancelled.")
            return 2
        print("WARNING: continuing in force mode.", file=sys.stderr)
        args.force_driver = True

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

    # Reference suggestions for new users.
    print("\n=== Reference suggestions ===")
    print("  - Read your physical MSVDD from HWiNFO64 or mVolt+ before continuing.")
    print("  - If you don't know it, 1150 mV is a common starting point on RTX 5090.")
    print("  - Author's stable starting combo (RTX 5090 / driver 610.62/610.88):")
    print("      XBAR +205 MHz / MSVDD +10 mV / Ratio 1.2 / VF auto wide range +88 MHz (224..253)")
    print("  - If the game crashes, lower XBAR to +178 or +150 first.")
    print("  - Other GPUs/VBIOS may need different values; start lower and verify.")

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
    vf_rec = _ctrl_rec(sample_flat)
    cur_vf = i32(get_u32(ctrl, vf_rec + 0x38)) if get_u32(ctrl, vf_rec) == 0xD else 0

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

    if not _confirm_step(args, "XBAR", new_freq - freq, safety.MAX_XBAR_STEP_KHZ):
        print("Cancelled.")
        return 1
    if not _confirm_step(args, "MSVDD", new_msvdd - msvdd, safety.MAX_MSVDD_STEP_UV, "uV"):
        print("Cancelled.")
        return 1
    if not _confirm_step(args, "VF", new_vf_freq - cur_vf, safety.MAX_VF_STEP_KHZ):
        print("Cancelled.")
        return 1
    if not _confirm_validated(args, "XBAR offset", safety.is_validated_xbar(new_freq),
                              f"{new_freq} kHz"):
        print("Cancelled.")
        return 1
    if not _confirm_validated(args, "MSVDD offset", safety.is_validated_msvdd(new_msvdd),
                              f"{new_msvdd} uV"):
        print("Cancelled.")
        return 1
    if not _confirm_validated(args, "Ratio", safety.is_validated_ratio(new_ratio),
                              f"{new_ratio:.4f}"):
        print("Cancelled.")
        return 1

    ans = input("Apply? [y/N] ").strip().lower()
    if ans not in ("y", "yes"):
        print("Cancelled.")
        return 1

    if not getattr(args, "force_driver", False) and not prop_rels.validate_prop_rels(api):
        print("ERROR: PropRels GET_INFO/GET_CONTROL validation failed; refusing to apply.", file=sys.stderr)
        return 2

    # Backups
    clk_buf, _, _ = clk_domains.read_clock_domains(api)
    prop_buf, _ = prop_rels.read_prop_rels(api)
    vf_pre = vf_points.get_control(api, active)
    backup_mod.save_binary_backup(BACKUP_DIR, "wizard_clk_pre", clk_buf,
                                  {"kind": "clk_domains", "gpu_index": api.gpu_index})
    backup_mod.save_binary_backup(BACKUP_DIR, "wizard_prop_pre", prop_buf,
                                  {"kind": "prop_rels", "gpu_index": api.gpu_index})
    backup_mod.save_binary_backup(BACKUP_DIR, "wizard_vf_pre", vf_pre,
                                  {"kind": "vf_control", "gpu_index": api.gpu_index})

    # Apply with rollback on failure
    try:
        clk_domains.write_clock_domains(api, new_freq, new_msvdd)
        prop_rels.write_prop_rels(api, prop_rels.ratio_float_to_raw(new_ratio))
        after_vf = vf_points.set_xbar_range(api, new_vf_start, new_vf_end, new_vf_freq)
        bad = []
        for flat in range(new_vf_start, new_vf_end + 1):
            rec = _ctrl_rec(flat)
            if get_u32(after_vf, rec) != 0xD:
                continue
            got = i32(get_u32(after_vf, rec + 0x38))
            if got != new_vf_freq:
                bad.append((flat, got))
        if bad:
            raise RuntimeError(f"VF readback mismatch on flats {bad[:10]}")
    except Exception as e:
        _safe_restore(lambda: clk_domains.restore_from_buf(api, clk_buf), "clk_domains", e)
        _safe_restore(lambda: prop_rels.restore_from_buf(api, prop_buf), "prop_rels", e)
        _safe_restore(lambda: vf_points.set_control(api, vf_pre), "vf_control", e)
        print(f"ERROR: apply failed, rolled back: {e}", file=sys.stderr)
        return 3

    print("Applied.")
    if getattr(args, "yes", False):
        print("--yes specified; skipping optional L2 test.")
    else:
        ans = input("Run L2 stability test now? [y/N] ").strip().lower()
        if ans in ("y", "yes"):
            ok = l2test.run_l2_test()
            return 0 if ok else 1
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


def cmd_probe(args, api: NvApi) -> int:
    ok = probe.probe_driver(api)
    return 0 if ok else 2


def cmd_crack(args, api: NvApi) -> int:
    candidates_path = os.path.join(APP_DIR, "candidates.json")
    ok = crack.crack_driver(api, candidates_path=candidates_path)
    return 0 if ok else 2


def cmd_l2_test(args, api: NvApi) -> int:
    ok = l2test.run_l2_test(
        blocks=args.blocks, threads=args.threads,
        stress_iters=args.stress_iters,
        idle_rounds=args.idle_rounds, load_rounds=args.load_rounds,
    )
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="xbar5090", description="RTX 50-series XBAR controls via private NvAPI")
    parser.add_argument("--gpu", type=int, default=0, help="GPU index (default 0)")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="only show errors")
    parser.add_argument("--log-file", help="write logs to this file")
    sub = parser.add_subparsers(dest="cmd")

    write_common = argparse.ArgumentParser(add_help=False)
    write_common.add_argument("--force-driver", action="store_true",
                              help="skip driver version check (dangerous)")
    write_common.add_argument("--yes", action="store_true",
                              help="skip step/validated confirmation prompts (dangerous)")

    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true", help="output JSON")
    p_status.set_defaults(func=cmd_status)
    p_x = sub.add_parser("set-xbar", parents=[write_common])
    p_x.add_argument("--freq-khz", type=int, required=True)
    p_x.add_argument("--msvdd-uv", type=int, default=0)
    p_x.set_defaults(func=cmd_set_xbar)
    p_r = sub.add_parser("set-ratio", parents=[write_common])
    p_r.add_argument("--ratio", type=float)
    p_r.add_argument("--raw", type=lambda x: int(x, 0))
    p_r.set_defaults(func=cmd_set_ratio)
    p_vs = sub.add_parser("vfp-status")
    p_vs.add_argument("--json", action="store_true", help="output JSON")
    p_vs.set_defaults(func=cmd_vfp_status)
    p_vr = sub.add_parser("vfp-set-range", parents=[write_common])
    p_vr.add_argument("--start", type=int, required=True)
    p_vr.add_argument("--end", type=int, required=True)
    p_vr.add_argument("--freq-khz", type=int, required=True)
    p_vr.set_defaults(func=cmd_vfp_set_range)
    p_va = sub.add_parser("vfp-auto-range", parents=[write_common],
                          help="auto-select a broad VF range around physical MSVDD and apply")
    p_va.add_argument("--msvdd-mv", type=float, help="current physical MSVDD in mV (prompts if omitted)")
    p_va.add_argument("--freq-khz", type=int, default=88000)
    p_va.add_argument("--width", type=int, default=15)
    p_va.set_defaults(func=cmd_vfp_auto_range)
    p_rest = sub.add_parser("vfp-restore", parents=[write_common])
    p_rest.add_argument("--backup", required=True)
    p_rest.set_defaults(func=cmd_vfp_restore)
    p_perf = sub.add_parser("perf")
    p_perf.add_argument("--json", action="store_true", help="output JSON")
    p_perf.set_defaults(func=cmd_perf)
    sub.add_parser("autostart-install").set_defaults(func=cmd_autostart_install)
    sub.add_parser("autostart-remove").set_defaults(func=cmd_autostart_remove)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("probe", help="auto-verify driver layout after a driver update (read-only)").set_defaults(func=cmd_probe)
    sub.add_parser("crack", help="auto-match driver function IDs from candidates.json (read-only probing)").set_defaults(func=cmd_crack)
    p_l2 = sub.add_parser("l2-test", help="run XBAR L2 data-integrity stability test")
    p_l2.add_argument("--blocks", type=int, default=1360)
    p_l2.add_argument("--threads", type=int, default=256)
    p_l2.add_argument("--stress-iters", type=int, default=100000)
    p_l2.add_argument("--idle-rounds", type=int, default=3)
    p_l2.add_argument("--load-rounds", type=int, default=3)
    p_l2.set_defaults(func=cmd_l2_test)
    sub.add_parser("wizard", parents=[write_common], help="interactive setup with ranges and current values").set_defaults(func=cmd_wizard)
    sub.add_parser("reset", parents=[write_common], help="reset XBAR/MSVDD/ratio/VF to driver defaults").set_defaults(func=cmd_reset)
    sub.add_parser("snapshot", help="save clk+prop+vf snapshot").set_defaults(func=cmd_snapshot)
    p_rs = sub.add_parser("restore-snapshot", parents=[write_common], help="restore clk+prop+vf snapshot")
    p_rs.add_argument("--snapshot", required=True)
    p_rs.set_defaults(func=cmd_restore_snapshot)
    p_ps = sub.add_parser("profile-save", help="save current settings as a named profile")
    p_ps.add_argument("name")
    p_ps.set_defaults(func=cmd_profile_save)
    p_pa = sub.add_parser("profile-apply", parents=[write_common], help="apply a named profile")
    p_pa.add_argument("name")
    p_pa.set_defaults(func=cmd_profile_apply)
    sub.add_parser("profile-list", help="list saved profiles").set_defaults(func=cmd_profile_list)

    # If no subcommand is given, launch the interactive wizard directly.
    # This makes double-click / "Run as administrator" on the exe work.
    parser.set_defaults(func=cmd_wizard)

    args = parser.parse_args(argv)
    _setup_logging(args)
    if getattr(args, "cmd", None) in {
        "set-xbar", "set-ratio", "vfp-set-range", "vfp-auto-range",
        "vfp-restore", "reset", "restore-snapshot", "wizard",
    }:
        _write_cooldown()
    try:
        api = _api(args.gpu)
    except Exception as e:
        print(f"Failed to init NvAPI: {e}", file=sys.stderr)
        return 2
    return args.func(args, api)


if __name__ == "__main__":
    sys.exit(main())
