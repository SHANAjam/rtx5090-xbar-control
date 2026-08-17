"""Clock domain control: XBAR frequency offset and XBAR-domain MSVDD offset.

Private NvAPI IDs:
  ClkDomainsGetControl 0xF58938F5
  ClkDomainsSetControl 0xD14B69CF
Version 0x000261A4 (V2) on the validated driver branch.
"""

from __future__ import annotations

from .nvapi import NvApi, get_u32, make_buffer, set_u32

CLK_DOMAINS_GET_CONTROL = 0xF58938F5
CLK_DOMAINS_SET_CONTROL = 0xD14B69CF
CLK_DOMAINS_VERSION = 0x000261A4
CLK_DOMAINS_BUFSIZE = 0x13000
CLK_DOMAINS_MASK = 0xFF
CLK_DOMAIN_ENTRY_STRIDE = 0x304
CLK_DOMAIN_ENTRY_BASE = 0x124
XBAR_DOMAIN_INDEX = 1
OFF_FREQ_KHZ = 0x114
OFF_MSVDD_UV = 0x11C


def read_clock_domains(api: NvApi):
    buf = make_buffer(CLK_DOMAINS_BUFSIZE)
    set_u32(buf, 0, CLK_DOMAINS_VERSION)
    set_u32(buf, 8, CLK_DOMAINS_MASK)
    rc = api.call(CLK_DOMAINS_GET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"ClkDomainsGetControl failed rc={rc}")
    base = CLK_DOMAIN_ENTRY_BASE + XBAR_DOMAIN_INDEX * CLK_DOMAIN_ENTRY_STRIDE
    freq = get_u32(buf, base + OFF_FREQ_KHZ)
    msvdd = get_u32(buf, base + OFF_MSVDD_UV)
    return buf, _i32(freq), _i32(msvdd)


def restore_from_buf(api: NvApi, buf) -> None:
    rc = api.call(CLK_DOMAINS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"ClkDomains restore failed rc={rc}")


def write_clock_domains(api: NvApi, freq_khz: int, msvdd_uv: int):
    buf, old_freq, old_msvdd = read_clock_domains(api)
    base = CLK_DOMAIN_ENTRY_BASE + XBAR_DOMAIN_INDEX * CLK_DOMAIN_ENTRY_STRIDE
    set_u32(buf, base + OFF_FREQ_KHZ, freq_khz & 0xFFFFFFFF)
    set_u32(buf, base + OFF_MSVDD_UV, msvdd_uv & 0xFFFFFFFF)
    rc = api.call(CLK_DOMAINS_SET_CONTROL, buf)
    if rc != 0:
        raise RuntimeError(f"ClkDomainsSetControl failed rc={rc}")
    _, new_freq, new_msvdd = read_clock_domains(api)
    return old_freq, old_msvdd, new_freq, new_msvdd


def _i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v if v < 0x80000000 else v - 0x100000000
