"""Read-only NvAPI Pstates20 parser.

This mirrors the private NvAPI Pstates20 layout used by Green Curve
(source/gpu_core.h) and exposes P0 clock-offset ranges plus per-domain
max clocks. It is read-only and intended for reverse-engineering the
core "SafeMax P0" ceiling and memory-clock limits on RTX 50-series GPUs.
"""

from __future__ import annotations

import ctypes

from .nvapi import NvApi

PSTATES20_GET = 0x6FF81213
PSTATES20_SET = 0x0F4DAE6B
PSTATES_INFO_EX = 0x6048B02F
POWER_POLICIES_GET_INFO = 0x34206D86
POWER_POLICIES_GET_STATUS = 0x355C8B8C
POWER_POLICIES_SET_STATUS = 0xAD95F5ED

NVAPI_GPU_PUBLIC_CLOCK_GRAPHICS = 0
NVAPI_GPU_PUBLIC_CLOCK_MEMORY = 4

NVAPI_GPU_PERF_PSTATE20_CLOCK_TYPE_SINGLE = 0
NVAPI_GPU_PERF_PSTATE20_CLOCK_TYPE_RANGE = 1

NVAPI_MAX_GPU_PSTATE20_PSTATES = 16
NVAPI_MAX_GPU_PSTATE20_CLOCKS = 8
NVAPI_MAX_GPU_PSTATE20_BASE_VOLTAGES = 4


class ParamDelta(ctypes.Structure):
    _fields_ = [
        ("value", ctypes.c_int),
        ("min", ctypes.c_int),
        ("max", ctypes.c_int),
    ]


class SingleClock(ctypes.Structure):
    _fields_ = [("freq_kHz", ctypes.c_uint)]


class RangeClock(ctypes.Structure):
    _fields_ = [
        ("minFreq_kHz", ctypes.c_uint),
        ("maxFreq_kHz", ctypes.c_uint),
        ("domainId", ctypes.c_uint),
        ("minVoltage_uV", ctypes.c_uint),
        ("maxVoltage_uV", ctypes.c_uint),
    ]


class ClockData(ctypes.Union):
    _fields_ = [
        ("single", SingleClock),
        ("range", RangeClock),
    ]


class ClockEntry(ctypes.Structure):
    _fields_ = [
        ("domainId", ctypes.c_uint),
        ("typeId", ctypes.c_uint),
        ("bIsEditable", ctypes.c_uint, 1),
        ("reserved", ctypes.c_uint, 31),
        ("freqDelta", ParamDelta),
        ("data", ClockData),
    ]


class BaseVoltageEntry(ctypes.Structure):
    _fields_ = [
        ("domainId", ctypes.c_uint),
        ("bIsEditable", ctypes.c_uint, 1),
        ("reserved", ctypes.c_uint, 31),
        ("volt_uV", ctypes.c_uint),
        ("voltDelta", ParamDelta),
    ]


class PstateEntry(ctypes.Structure):
    _fields_ = [
        ("pstateId", ctypes.c_uint),
        ("bIsEditable", ctypes.c_uint, 1),
        ("reserved", ctypes.c_uint, 31),
        ("clocks", ClockEntry * NVAPI_MAX_GPU_PSTATE20_CLOCKS),
        ("baseVoltages", BaseVoltageEntry * NVAPI_MAX_GPU_PSTATE20_BASE_VOLTAGES),
    ]


class Pstates20Ov(ctypes.Structure):
    _fields_ = [
        ("numVoltages", ctypes.c_uint),
        ("voltages", BaseVoltageEntry * NVAPI_MAX_GPU_PSTATE20_BASE_VOLTAGES),
    ]


class Pstates20Info(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint),
        ("bIsEditable", ctypes.c_uint, 1),
        ("reserved", ctypes.c_uint, 31),
        ("numPstates", ctypes.c_uint),
        ("numClocks", ctypes.c_uint),
        ("numBaseVoltages", ctypes.c_uint),
        ("pstates", PstateEntry * NVAPI_MAX_GPU_PSTATE20_PSTATES),
        ("ov", Pstates20Ov),
    ]


def _version(ver: int) -> int:
    return ctypes.sizeof(Pstates20Info) | (ver << 16)


def _get_func(api: NvApi, fid: int):
    fn = api._fn(fid)
    if not fn:
        raise RuntimeError(f"NvAPI function missing: {fid:#x}")
    return ctypes.cast(fn, ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(Pstates20Info)))


def call_pstates_get(api: NvApi) -> Pstates20Info:
    func = _get_func(api, PSTATES20_GET)
    info = Pstates20Info()
    info.version = _version(3)
    rc = func(api.gpu, ctypes.byref(info))
    if rc != 0:
        info = Pstates20Info()
        info.version = _version(2)
        rc = func(api.gpu, ctypes.byref(info))
    if rc != 0:
        raise RuntimeError(f"Pstates20 GET failed rc={rc}")
    return info


def call_pstates_set(api: NvApi, info: Pstates20Info) -> int:
    func = _get_func(api, PSTATES20_SET)
    return func(api.gpu, ctypes.byref(info))


def noop_pstates_set(api: NvApi) -> dict:
    """Read current Pstates20 and submit it back unchanged (no-op test)."""
    before = call_pstates_get(api)
    rc = call_pstates_set(api, before)
    after = call_pstates_get(api)
    same = bytes(before) == bytes(after)
    return {"rc": rc, "same": same, "before_version": before.version, "after_version": after.version}


# Raw PState20 V2 layout (empirically from gpu-auto-optimizer backend).
_PSTATE20_BUF_SIZE = 7416
_PSTATE20_VERSION_V2 = _PSTATE20_BUF_SIZE | (2 << 16)
_OFF_VERSION = 0
_OFF_EDITABLE = 4
_OFF_NUM_PSTATES = 8
_OFF_NUM_CLOCKS = 12
_OFF_NUM_BASE_VOLTS = 16
_OFF_PSTATE0 = 20
_PSTATE_HEADER_SIZE = 8
_CLOCK_ENTRY_SIZE = 44
_CLOCK_DELTA_OFFSET = 12
_CLOCK_MAXFREQ_OFFSET = 28

# P0 clock entry bases.
_P0_CORE_ENTRY = _OFF_PSTATE0 + _PSTATE_HEADER_SIZE + 0 * _CLOCK_ENTRY_SIZE
_P0_MEM_ENTRY = _OFF_PSTATE0 + _PSTATE_HEADER_SIZE + 1 * _CLOCK_ENTRY_SIZE


def read_pstate20_raw(api: NvApi) -> bytes:
    fn = api._fn(PSTATES20_GET)
    if not fn:
        raise RuntimeError(f"Pstates20 GET missing: {PSTATES20_GET:#x}")
    func = ctypes.cast(fn, ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p))
    buf = (ctypes.c_ubyte * _PSTATE20_BUF_SIZE)()
    ctypes.memset(buf, 0, _PSTATE20_BUF_SIZE)
    ctypes.cast(ctypes.byref(buf), ctypes.POINTER(ctypes.c_uint32))[0] = _PSTATE20_VERSION_V2
    rc = func(api.gpu, ctypes.byref(buf))
    if rc != 0:
        raise RuntimeError(f"Pstates20 GET raw failed rc={rc}")
    return bytes(buf)


def write_pstate20_raw(api: NvApi, data: bytes) -> int:
    fn = api._fn(PSTATES20_SET)
    if not fn:
        raise RuntimeError(f"Pstates20 SET missing: {PSTATES20_SET:#x}")
    func = ctypes.cast(fn, ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p))
    buf = (ctypes.c_ubyte * _PSTATE20_BUF_SIZE)()
    ctypes.memmove(buf, data, min(len(data), _PSTATE20_BUF_SIZE))
    return func(api.gpu, ctypes.byref(buf))


def _u32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little")


def _i32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little", signed=True)


def _set_u32(data: bytearray, off: int, val: int) -> None:
    data[off:off + 4] = int(val).to_bytes(4, "little", signed=False)


def _set_i32(data: bytearray, off: int, val: int) -> None:
    data[off:off + 4] = int(val).to_bytes(4, "little", signed=True)


def raw_noop_pstates_set(api: NvApi) -> dict:
    """Minimal V2 SET with the current buffer unchanged (no-op test)."""
    current = read_pstate20_raw(api)
    buf = bytearray(current)
    _set_u32(buf, _OFF_VERSION, _PSTATE20_VERSION_V2)
    _set_u32(buf, _OFF_EDITABLE, 1)
    _set_u32(buf, _OFF_NUM_PSTATES, 1)
    rc = write_pstate20_raw(api, bytes(buf))
    after = read_pstate20_raw(api)
    same = bytes(buf) == after
    return {"rc": rc, "same": same, "version": _u32(after, _OFF_VERSION)}


# --- V3 raw helpers (Blackwell Pstates20 layout) ---

_PSTATE20_VERSION_V3 = ctypes.sizeof(Pstates20Info) | (3 << 16)


def read_pstate20_v3_raw(api: NvApi) -> bytes:
    info = call_pstates_get(api)
    return bytes(info)


def write_pstate20_v3_raw(api: NvApi, data: bytes) -> int:
    fn = api._fn(PSTATES20_SET)
    if not fn:
        raise RuntimeError(f"Pstates20 SET missing: {PSTATES20_SET:#x}")
    func = ctypes.cast(fn, ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p))
    buf = (ctypes.c_ubyte * _PSTATE20_BUF_SIZE)()
    ctypes.memmove(buf, data, min(len(data), _PSTATE20_BUF_SIZE))
    return func(api.gpu, ctypes.byref(buf))


def v3_noop_pstates_set(api: NvApi) -> dict:
    """Minimal V3 SET with the current V3 buffer unchanged (no-op test)."""
    current = read_pstate20_v3_raw(api)
    buf = bytearray(current)
    _set_u32(buf, _OFF_VERSION, _PSTATE20_VERSION_V3)
    _set_u32(buf, _OFF_EDITABLE, 1)
    _set_u32(buf, _OFF_NUM_PSTATES, 1)
    rc = write_pstate20_v3_raw(api, bytes(buf))
    after = read_pstate20_v3_raw(api)
    same = bytes(buf) == after
    return {"rc": rc, "same": same, "version": _u32(after, _OFF_VERSION)}


def set_pstate20_limits(
    api: NvApi,
    core_max_khz: int | None = None,
    mem_max_khz: int | None = None,
    core_delta_khz: int = 0,
    mem_delta_khz: int = 0,
    core_base_khz: int | None = None,
    mem_base_khz: int | None = None,
) -> dict:
    """Write P0 clock limits/deltas/bases through the raw PState20 V2 SET path.

    Only P0 is submitted (numPstates=1), matching the empirically working
    gpu-auto-optimizer layout. This is a real write; use with care.
    """
    current = read_pstate20_raw(api)
    buf = bytearray(current)
    _set_u32(buf, _OFF_VERSION, _PSTATE20_VERSION_V2)
    _set_u32(buf, _OFF_EDITABLE, 1)
    _set_u32(buf, _OFF_NUM_PSTATES, 1)
    _set_i32(buf, _P0_CORE_ENTRY + _CLOCK_DELTA_OFFSET, core_delta_khz)
    _set_i32(buf, _P0_MEM_ENTRY + _CLOCK_DELTA_OFFSET, mem_delta_khz)
    if core_max_khz is not None:
        _set_u32(buf, _P0_CORE_ENTRY + _CLOCK_MAXFREQ_OFFSET, core_max_khz)
    if mem_max_khz is not None:
        _set_u32(buf, _P0_MEM_ENTRY + _CLOCK_MAXFREQ_OFFSET, mem_max_khz)
    # Base frequency is at +24 within a clock entry.
    if core_base_khz is not None:
        _set_u32(buf, _P0_CORE_ENTRY + 24, core_base_khz)
    if mem_base_khz is not None:
        _set_u32(buf, _P0_MEM_ENTRY + 24, mem_base_khz)
    rc = write_pstate20_raw(api, bytes(buf))
    after = read_pstate20_raw(api)
    return {
        "rc": rc,
        "core_delta_khz": _i32(after, _P0_CORE_ENTRY + _CLOCK_DELTA_OFFSET),
        "mem_delta_khz": _i32(after, _P0_MEM_ENTRY + _CLOCK_DELTA_OFFSET),
        "core_max_khz": _u32(after, _P0_CORE_ENTRY + _CLOCK_MAXFREQ_OFFSET),
        "mem_max_khz": _u32(after, _P0_MEM_ENTRY + _CLOCK_MAXFREQ_OFFSET),
        "core_base_khz": _u32(after, _P0_CORE_ENTRY + 24),
        "mem_base_khz": _u32(after, _P0_MEM_ENTRY + 24),
    }


def probe_related_ids(api: NvApi) -> dict:
    """Check which private NvAPI IDs related to P-states/power are exported."""
    ids = {
        "pstates20_get": PSTATES20_GET,
        "pstates20_set": PSTATES20_SET,
        "pstates_info_ex": PSTATES_INFO_EX,
        "power_policies_get_info": POWER_POLICIES_GET_INFO,
        "power_policies_get_status": POWER_POLICIES_GET_STATUS,
        "power_policies_set_status": POWER_POLICIES_SET_STATUS,
    }
    result = {}
    for name, fid in ids.items():
        try:
            result[name] = api._fn(fid) is not None
        except Exception:
            result[name] = False
    return result


def _clock_max_khz(entry: ClockEntry) -> int:
    if entry.typeId == NVAPI_GPU_PERF_PSTATE20_CLOCK_TYPE_SINGLE:
        return entry.data.single.freq_kHz
    if entry.typeId == NVAPI_GPU_PERF_PSTATE20_CLOCK_TYPE_RANGE:
        return entry.data.range.maxFreq_kHz
    return 0


def read_pstates(api: NvApi) -> dict:
    """Call the private NvAPI Pstates20 GET and return a parsed dictionary."""
    fn = api._fn(PSTATES20_GET)
    if not fn:
        raise RuntimeError(f"Pstates20 GET missing for {PSTATES20_GET:#x}")

    func_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(Pstates20Info))
    func = ctypes.cast(fn, func_type)

    info = Pstates20Info()
    info.version = _version(3)
    rc = func(api.gpu, ctypes.byref(info))
    if rc != 0:
        info = Pstates20Info()
        info.version = _version(2)
        rc = func(api.gpu, ctypes.byref(info))
    if rc != 0:
        raise RuntimeError(f"Pstates20 GET failed rc={rc}")

    parsed = {
        "version": info.version,
        "numPstates": info.numPstates,
        "numClocks": info.numClocks,
        "pstates": [],
    }
    gpu_curve_ranges = []
    p0_ranges = []
    mem_max_khz = 0
    for pi in range(min(info.numPstates, NVAPI_MAX_GPU_PSTATE20_PSTATES)):
        ps = info.pstates[pi]
        clocks = []
        for ci in range(min(info.numClocks, NVAPI_MAX_GPU_PSTATE20_CLOCKS)):
            clk = ps.clocks[ci]
            max_khz = _clock_max_khz(clk)
            clocks.append({
                "domainId": clk.domainId,
                "typeId": clk.typeId,
                "editable": bool(clk.bIsEditable),
                "freqDeltaKHz": clk.freqDelta.value,
                "freqDeltaMinKHz": clk.freqDelta.min,
                "freqDeltaMaxKHz": clk.freqDelta.max,
                "maxFreqKHz": max_khz,
            })
            if clk.domainId == NVAPI_GPU_PUBLIC_CLOCK_GRAPHICS and clk.bIsEditable:
                rng = (clk.freqDelta.min, clk.freqDelta.max)
                gpu_curve_ranges.append(rng)
                if ps.pstateId == 0:
                    p0_ranges.append(rng)
            if clk.domainId == NVAPI_GPU_PUBLIC_CLOCK_MEMORY:
                if max_khz > mem_max_khz:
                    mem_max_khz = max_khz
        parsed["pstates"].append({
            "pstateId": ps.pstateId,
            "editable": bool(ps.bIsEditable),
            "clocks": clocks,
        })

    parsed["gpuCurveOffsetMinKHz"] = min((r[0] for r in gpu_curve_ranges), default=0)
    parsed["gpuCurveOffsetMaxKHz"] = max((r[1] for r in gpu_curve_ranges), default=0)
    parsed["p0OffsetMinKHz"] = min((r[0] for r in p0_ranges), default=0)
    parsed["p0OffsetMaxKHz"] = max((r[1] for r in p0_ranges), default=0)
    parsed["memoryMaxKHz"] = mem_max_khz
    return parsed
