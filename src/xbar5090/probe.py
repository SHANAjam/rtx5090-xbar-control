"""Driver auto-probe / compatibility verification.

This module does NOT blindly "crack" a new driver.  It automates the safe
first step of adapting to a driver update:

1. Read the current NVIDIA driver version.
2. Verify that every validated private NvAPI function ID is still exported by
   nvapi_QueryInterface.
3. Perform read-only calls and check that the returned values are plausible.
4. If everything passes, write a driver_profile.json so write commands can be
   allowed on this driver.
5. If anything fails, refuse to write and tell the user the new layout must be
   reverse-engineered manually.

The validated profile is for driver 610.62.  A new driver may keep the same
IDs (common) or change them (then this tool will fail safely).
"""

from __future__ import annotations

import json
import os

from . import clk_domains, driver_check, perf_limits, prop_rels, vf_points
from .nvapi import NvApi

# The known-good IDs/versions from the validated RTX 5090 / driver 610.62.
# If a driver update keeps these working, probe will create a new profile.
KNOWN_PROFILE = {
    "driver_prefix": "/".join(driver_check.VALIDATED_DRIVER_PREFIXES),
    "clk_domains": {
        "get": clk_domains.CLK_DOMAINS_GET_CONTROL,
        "set": clk_domains.CLK_DOMAINS_SET_CONTROL,
        "version": clk_domains.CLK_DOMAINS_VERSION,
        "bufsize": clk_domains.CLK_DOMAINS_BUFSIZE,
        "mask": clk_domains.CLK_DOMAINS_MASK,
        "entry_base": clk_domains.CLK_DOMAIN_ENTRY_BASE,
        "entry_stride": clk_domains.CLK_DOMAIN_ENTRY_STRIDE,
        "xbar_domain_index": clk_domains.XBAR_DOMAIN_INDEX,
        "off_freq_khz": clk_domains.OFF_FREQ_KHZ,
        "off_msvdd_uv": clk_domains.OFF_MSVDD_UV,
    },
    "prop_rels": {
        "get": prop_rels.PROP_RELS_GET_CONTROL,
        "set": prop_rels.PROP_RELS_SET_CONTROL,
        "version": prop_rels.PROP_RELS_VERSION,
        "bufsize": prop_rels.PROP_RELS_BUFSIZE,
        "entry_base": prop_rels.PROP_ENTRY_BASE,
        "entry_stride": prop_rels.PROP_ENTRY_STRIDE,
        "off_ratio": prop_rels.PROP_OFF_RATIO,
        "default_ratio_raw": prop_rels.DEFAULT_RATIO_RAW,
    },
    "vf_points": {
        "info": vf_points.VF_INFO,
        "status": vf_points.VF_STATUS,
        "get_control": vf_points.VF_GET_CONTROL,
        "set_control": vf_points.VF_SET_CONTROL,
        "info_ver": vf_points.VF_INFO_VER,
        "status_ver": vf_points.VF_STATUS_VER,
        "ctrl_ver": vf_points.VF_CTRL_VER,
        "status_rec_base": vf_points.STATUS_REC_BASE,
        "status_rec_stride": vf_points.STATUS_REC_STRIDE,
        "ctrl_rec_base": vf_points.CTRL_REC_BASE,
        "ctrl_rec_stride": vf_points.CTRL_REC_STRIDE,
        "xbar_start": vf_points.XBAR_START,
        "xbar_end": vf_points.XBAR_END,
    },
    "perf": {
        "get": perf_limits.PERF_GET,
        "version": perf_limits.PERF_VER,
    },
}


def _fn_exists(api: NvApi, fid: int) -> bool:
    try:
        return api._fn(fid) is not None
    except Exception:
        return False


def _plausible_freq(freq_khz: int) -> bool:
    return -1_000_000 <= freq_khz <= 1_000_000


def _plausible_msvdd(msvdd_uv: int) -> bool:
    return -100_000 <= msvdd_uv <= 100_000


def _plausible_ratio(raw: int) -> bool:
    return 0 <= raw <= 2 * 65536


def probe_driver(api: NvApi, profile_path: str | None = None) -> bool:
    """Run read-only probes.  Returns True only if the known layout still works."""
    print("=== xbar5090 driver auto-probe ===")
    version = driver_check.get_driver_version()
    if not version:
        print("ERROR: could not read driver version from nvidia-smi.", file=__import__("sys").stderr)
        return False
    print(f"Driver version : {version}")
    print(f"Validated base : {'/'.join(driver_check.VALIDATED_DRIVER_PREFIXES)}")

    ok = True
    checks = []

    # 1. Function pointers
    for label, fid in [
        ("ClkDomainsGet", KNOWN_PROFILE["clk_domains"]["get"]),
        ("ClkDomainsSet", KNOWN_PROFILE["clk_domains"]["set"]),
        ("PropRelsGet", KNOWN_PROFILE["prop_rels"]["get"]),
        ("PropRelsSet", KNOWN_PROFILE["prop_rels"]["set"]),
        ("VF_INFO", KNOWN_PROFILE["vf_points"]["info"]),
        ("VF_STATUS", KNOWN_PROFILE["vf_points"]["status"]),
        ("VF_GET", KNOWN_PROFILE["vf_points"]["get_control"]),
        ("VF_SET", KNOWN_PROFILE["vf_points"]["set_control"]),
        ("PERF_GET", KNOWN_PROFILE["perf"]["get"]),
    ]:
        exists = _fn_exists(api, fid)
        checks.append((label, exists, f"{fid:#x} {'OK' if exists else 'MISSING'}"))
        if not exists:
            ok = False

    # 2. Read probes
    try:
        _, freq, msvdd = clk_domains.read_clock_domains(api)
        good = _plausible_freq(freq) and _plausible_msvdd(msvdd)
        checks.append(("ClkDomains read", good, f"freq={freq} kHz msvdd={msvdd} uV"))
        if not good:
            ok = False
    except Exception as e:
        checks.append(("ClkDomains read", False, str(e)))
        ok = False

    try:
        _, raw = prop_rels.read_prop_rels(api)
        good = _plausible_ratio(raw)
        checks.append(("PropRels read", good, f"ratio_raw={raw}"))
        if not good:
            ok = False
    except Exception as e:
        checks.append(("PropRels read", False, str(e)))
        ok = False

    try:
        active = vf_points.active_mask(api)
        good = len(active) > 0
        checks.append(("VF active mask", good, f"active={len(active)}"))
        if not good:
            ok = False
    except Exception as e:
        checks.append(("VF active mask", False, str(e)))
        ok = False

    try:
        bank = vf_points.detect_xbar_bank(api)
        good = bank is not None
        checks.append(("VF XBAR bank", good, f"{bank}" if bank else "not detected"))
        if not good:
            ok = False
    except Exception as e:
        checks.append(("VF XBAR bank", False, str(e)))
        ok = False

    try:
        buf = perf_limits.get_perf_limits(api)
        # Only check that the call succeeded; entries are layout-specific.
        checks.append(("PERF read", True, f"buf={len(bytes(buf))} bytes"))
    except Exception as e:
        checks.append(("PERF read", False, str(e)))
        ok = False

    for label, good, detail in checks:
        print(f"  [{'OK' if good else 'FAIL'}] {label}: {detail}")

    if not ok:
        print("\nRESULT: FAIL")
        print("The validated layout does NOT match this driver.")
        print("Refusing to allow writes. Do not force-write on an unknown layout.")
        return False

    # 3. Write profile
    if profile_path is None:
        if getattr(__import__("sys"), "frozen", False):
            base_dir = os.path.dirname(__import__("sys").executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        profile_path = os.path.join(base_dir, "driver_profile.json")

    profile = dict(KNOWN_PROFILE)
    profile["detected_driver"] = version
    profile["probe_ok"] = True
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"\nRESULT: PASS")
    print(f"Wrote driver profile: {profile_path}")
    print("Write commands may now be used on this driver (same layout as validated profile).")
    return True
