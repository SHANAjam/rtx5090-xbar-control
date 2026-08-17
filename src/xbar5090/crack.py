"""Safe driver auto-crack via candidate matching.

This is NOT a random brute-force reverse engineering tool.  It only calls
NvAPI function IDs that are listed in a trusted candidate table.  Randomly
calling unknown IDs is dangerous because a "GET" candidate may actually be a
"SET" function and could modify hardware.

How it works:
1. Load candidate IDs from candidates.json (or built-in defaults).
2. For each read (GET) function, try every candidate ID with a read-only
   probe and pick the first one that returns plausible data.
3. For each write (SET) function, only check that a listed candidate ID still
   exists (we never call it during probing).
4. If every function is found, write a driver_profile.json.
5. If any function is missing, refuse and tell the user to add the new IDs to
   candidates.json.

This makes driver updates work automatically when the new IDs are known to
the community and added to the candidate table.
"""

from __future__ import annotations

import json
import os
import sys

from . import clk_domains, driver_check, perf_limits, prop_rels, vf_points
from .nvapi import NvApi, get_u32, make_buffer, set_u32

# Built-in candidate table.  Users can add newly discovered IDs to
# candidates.json without changing code.
DEFAULT_CANDIDATES = {
    "clk_get": [clk_domains.CLK_DOMAINS_GET_CONTROL],
    "clk_set": [clk_domains.CLK_DOMAINS_SET_CONTROL],
    "prop_get": [prop_rels.PROP_RELS_GET_CONTROL],
    "prop_set": [prop_rels.PROP_RELS_SET_CONTROL],
    "vf_info": [vf_points.VF_INFO],
    "vf_status": [vf_points.VF_STATUS],
    "vf_get": [vf_points.VF_GET_CONTROL],
    "vf_set": [vf_points.VF_SET_CONTROL],
    "perf_get": [perf_limits.PERF_GET],
}

# How many candidate IDs to try before giving up (safety cap).
MAX_CANDIDATES_PER_FN = 64


def _load_candidates(path: str | None) -> dict:
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults so a partial file still works.
        merged = {k: list(dict.fromkeys(list(DEFAULT_CANDIDATES.get(k, [])) + list(data.get(k, []))))
                  for k in DEFAULT_CANDIDATES}
        # Include any extra keys the user added.
        for k, v in data.items():
            if k not in merged:
                merged[k] = list(v)
        return merged
    return DEFAULT_CANDIDATES


def _fn_exists(api: NvApi, fid: int) -> bool:
    try:
        return api._fn(fid) is not None
    except Exception:
        return False


def _try_clk_get(api: NvApi, fid: int) -> bool:
    try:
        buf = make_buffer(clk_domains.CLK_DOMAINS_BUFSIZE)
        set_u32(buf, 0, clk_domains.CLK_DOMAINS_VERSION)
        set_u32(buf, 8, clk_domains.CLK_DOMAINS_MASK)
        rc = api.call(fid, buf)
        if rc != 0:
            return False
        base = clk_domains.CLK_DOMAIN_ENTRY_BASE + clk_domains.XBAR_DOMAIN_INDEX * clk_domains.CLK_DOMAIN_ENTRY_STRIDE
        freq_raw = get_u32(buf, base + clk_domains.OFF_FREQ_KHZ)
        msvdd_raw = get_u32(buf, base + clk_domains.OFF_MSVDD_UV)
        freq = freq_raw if freq_raw < 0x80000000 else freq_raw - 0x100000000
        msvdd = msvdd_raw if msvdd_raw < 0x80000000 else msvdd_raw - 0x100000000
        return -1_000_000 <= freq <= 1_000_000 and -100_000 <= msvdd <= 100_000
    except Exception:
        return False


def _try_prop_get(api: NvApi, fid: int) -> bool:
    try:
        buf = make_buffer(prop_rels.PROP_RELS_BUFSIZE)
        set_u32(buf, 0, prop_rels.PROP_RELS_VERSION)
        set_u32(buf, 4, prop_rels.PROP_RELS_MASK)
        rc = api.call(fid, buf)
        if rc != 0:
            return False
        raw = get_u32(buf, prop_rels.PROP_ENTRY_BASE + prop_rels.PROP_OFF_RATIO)
        return 0 <= raw <= 2 * 65536
    except Exception:
        return False


def _try_vf_info(api: NvApi, fid: int) -> bool:
    try:
        buf = make_buffer(vf_points.VF_INFO_VER)
        set_u32(buf, 0, vf_points.VF_INFO_VER)
        rc = api.call(fid, buf)
        if rc != 0:
            return False
        count = 0
        for i in range(2048):
            if get_u32(buf, 4 + 4 * (i // 32)) & (1 << (i % 32)):
                count += 1
        return count > 0
    except Exception:
        return False


_CURRENT_VF_INFO = vf_points.VF_INFO
_CURRENT_VF_STATUS = vf_points.VF_STATUS


def _try_vf_status(api: NvApi, fid: int) -> bool:
    try:
        active = vf_points.active_mask(api, info_id=_CURRENT_VF_INFO)
        buf = make_buffer(vf_points.VF_STATUS_VER)
        set_u32(buf, 0, vf_points.VF_STATUS_VER)
        for i in active:
            off = 4 + 4 * (i // 32)
            set_u32(buf, off, get_u32(buf, off) | (1 << (i % 32)))
        rc = api.call(fid, buf)
        return rc == 0
    except Exception:
        return False


def _try_vf_get(api: NvApi, fid: int) -> bool:
    try:
        active = vf_points.active_mask(api, info_id=_CURRENT_VF_INFO)
        buf = make_buffer(vf_points.VF_CTRL_VER)
        set_u32(buf, 0, vf_points.VF_CTRL_VER)
        for i in active:
            off = 4 + 4 * (i // 32)
            set_u32(buf, off, get_u32(buf, off) | (1 << (i % 32)))
        rc = api.call(fid, buf)
        if rc != 0:
            return False
        bank = vf_points.detect_xbar_bank(api, info_id=_CURRENT_VF_INFO, status_id=_CURRENT_VF_STATUS)
        return bank is not None
    except Exception:
        return False


def _try_perf_get(api: NvApi, fid: int) -> bool:
    try:
        buf = make_buffer(perf_limits.PERF_VER)
        set_u32(buf, 0, perf_limits.PERF_VER)
        rc = api.call(fid, buf)
        return rc == 0
    except Exception:
        return False


def _pick(api: NvApi, label: str, candidates: list[int], tester, is_set: bool = False) -> int | None:
    tried = 0
    for fid in candidates:
        if tried >= MAX_CANDIDATES_PER_FN:
            break
        tried += 1
        if is_set:
            if _fn_exists(api, fid):
                print(f"  [OK] {label}: {fid:#x} (exists, not called)")
                return fid
        else:
            if tester(api, fid):
                print(f"  [OK] {label}: {fid:#x}")
                return fid
    print(f"  [FAIL] {label}: no candidate matched")
    return None


def crack_driver(api: NvApi, candidates_path: str | None = None) -> bool:
    print("=== xbar5090 driver auto-crack (candidate matching) ===")
    version = driver_check.get_driver_version()
    print(f"Driver version : {version or 'unknown'}")

    cands = _load_candidates(candidates_path)
    found = {}

    found["clk_get"] = _pick(api, "ClkDomainsGet", cands.get("clk_get", []), _try_clk_get)
    found["clk_set"] = _pick(api, "ClkDomainsSet", cands.get("clk_set", []), None, is_set=True)
    found["prop_get"] = _pick(api, "PropRelsGet", cands.get("prop_get", []), _try_prop_get)
    found["prop_set"] = _pick(api, "PropRelsSet", cands.get("prop_set", []), None, is_set=True)
    found["vf_info"] = _pick(api, "VF_INFO", cands.get("vf_info", []), _try_vf_info)
    if found["vf_info"] is not None:
        global _CURRENT_VF_INFO
        _CURRENT_VF_INFO = found["vf_info"]
    found["vf_status"] = _pick(api, "VF_STATUS", cands.get("vf_status", []), _try_vf_status)
    if found["vf_status"] is not None:
        global _CURRENT_VF_STATUS
        _CURRENT_VF_STATUS = found["vf_status"]
    found["vf_get"] = _pick(api, "VF_GET", cands.get("vf_get", []), _try_vf_get)
    found["vf_set"] = _pick(api, "VF_SET", cands.get("vf_set", []), None, is_set=True)
    found["perf_get"] = _pick(api, "PERF_GET", cands.get("perf_get", []), _try_perf_get)

    missing = [k for k, v in found.items() if v is None]
    if missing:
        print(f"\nRESULT: FAIL")
        print(f"Missing: {', '.join(missing)}")
        print("Add the new driver's IDs to candidates.json and run again.")
        print("Do NOT write on this driver until all functions are matched.")
        return False

    profile = {
        "driver_prefix": "/".join(driver_check.VALIDATED_DRIVER_PREFIXES),
        "detected_driver": version,
        "probe_ok": True,
        "clk_domains": {
            "get": found["clk_get"],
            "set": found["clk_set"],
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
            "get": found["prop_get"],
            "set": found["prop_set"],
            "version": prop_rels.PROP_RELS_VERSION,
            "bufsize": prop_rels.PROP_RELS_BUFSIZE,
            "entry_base": prop_rels.PROP_ENTRY_BASE,
            "entry_stride": prop_rels.PROP_ENTRY_STRIDE,
            "off_ratio": prop_rels.PROP_OFF_RATIO,
            "default_ratio_raw": prop_rels.DEFAULT_RATIO_RAW,
        },
        "vf_points": {
            "info": found["vf_info"],
            "status": found["vf_status"],
            "get_control": found["vf_get"],
            "set_control": found["vf_set"],
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
            "get": found["perf_get"],
            "version": perf_limits.PERF_VER,
        },
    }

    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    profile_path = os.path.join(base_dir, "driver_profile.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(f"\nRESULT: PASS")
    print(f"Wrote driver profile: {profile_path}")
    print("All functions matched. Write commands may now be used.")
    return True
