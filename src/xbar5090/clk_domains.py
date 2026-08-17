"""Clock domain control: XBAR frequency offset and XBAR-domain MSVDD offset.

Private NvAPI IDs:
  ClkDomainsGetControl 0xF58938F5
  ClkDomainsSetControl 0xD14B69CF
Version 0x000261A4 (V2) on the validated driver branch.
"""

from __future__ import annotations

from .nvapi import NvApi, get_u32, i32, make_buffer, set_u32

CLK_DOMAINS_GET_CONTROL = 0xF58938F5
CLK_DOMAINS_SET_CONTROL = 0xD14B69CF
CLK_DOMAINS_VERSION = 0x000261A4
CLK_DOMAINS_BUFSIZE = 0x13000
CLK_DOMAINS_MASK = 0xFF
CLK_DOMAIN_ENTRY_STRIDE = 0x304
CLK_DOMAIN_ENTRY_BASE = 0x124
# XBAR domain index is hardcoded (validated on RTX 5090 / driver 610.62/610.88).
# LACT uses GET_INFO to discover this dynamically; on Windows we do not yet
# have a verified ClkDomainsGetInfo layout, but index 1 matches both RM and
# NvAPI on the validated cards, so risk is considered low.
XBAR_DOMAIN_INDEX = 1
OFF_FREQ_KHZ = 0x114
OFF_MSVDD_UV = 0x11C

# Physical frequency measurement (CLK_MEASURE_FREQ).
CLK_MEASURE_FREQ = 0x527FC458
CLK_MEASURE_VER = 0x1000C
CLK_MEASURE_MASK_OFF = 0x4
CLK_MEASURE_FREQ_OFF = 0x8
XBAR_MEASURE_MASK = 0x2


def measure_xbar_khz(api: NvApi) -> int:
    """Read the physical XBAR clock in kHz via CLK_MEASURE_FREQ."""
    buf = make_buffer(CLK_MEASURE_VER)
    set_u32(buf, 0, CLK_MEASURE_VER)
    set_u32(buf, CLK_MEASURE_MASK_OFF, XBAR_MEASURE_MASK)
    rc = api.call(CLK_MEASURE_FREQ, buf)
    if rc != 0:
        raise RuntimeError(f"CLK_MEASURE_FREQ failed rc={rc}")
    return get_u32(buf, CLK_MEASURE_FREQ_OFF)


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
    return buf, i32(freq), i32(msvdd)


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
