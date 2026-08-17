"""Low-level NvAPI access helpers.

These functions wrap nvapi64.dll's QueryInterface-based private API dispatch.
Private interface IDs and structure layouts are driver-branch specific.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

NVAPI64 = r"C:\Windows\System32\nvapi64.dll"

QI_INIT = 0x0150E828
QI_ENUM_GPUS = 0xE5AC921F

_QI_RESTYPE = ctypes.c_void_p
_QI_ARGTYPES = [ctypes.c_uint32]


class NvApiError(RuntimeError):
    """Raised when an NvAPI call fails."""


class NvApi:
    """Thin wrapper around nvapi_QueryInterface + private function pointers."""

    def __init__(self, nvapi64: str = NVAPI64, gpu_index: int = 0) -> None:
        self._nv = ctypes.WinDLL(nvapi64)
        self._qi = self._nv.nvapi_QueryInterface
        self._qi.restype = _QI_RESTYPE
        self._qi.argtypes = _QI_ARGTYPES
        self.gpu: ctypes.c_void_p | None = None
        self.gpu_index = gpu_index
        self._init()

    def _fn(self, fid: int) -> int:
        ptr = self._qi(fid)
        if not ptr:
            raise NvApiError(f"nvapi_QueryInterface returned NULL for {fid:#x}")
        return ctypes.cast(ptr, ctypes.c_void_p).value

    def _init(self) -> None:
        init_fn = ctypes.cast(self._fn(QI_INIT), ctypes.WINFUNCTYPE(ctypes.c_int))
        rc = init_fn()
        if rc != 0:
            raise NvApiError(f"NvAPI_Initialize failed rc={rc}")

        enum_fn_type = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint32),
        )
        enum_fn = ctypes.cast(self._fn(QI_ENUM_GPUS), enum_fn_type)
        handles = (ctypes.c_void_p * 64)()
        count = ctypes.c_uint32()
        rc = enum_fn(handles, ctypes.byref(count))
        if rc != 0 or count.value == 0:
            raise NvApiError(f"EnumPhysicalGPUs failed rc={rc} count={count.value}")
        if self.gpu_index >= count.value:
            raise NvApiError(f"GPU index {self.gpu_index} out of range (count={count.value})")
        self.gpu = ctypes.c_void_p(handles[self.gpu_index])

    def call(self, fid: int, buf: ctypes.Array) -> int:
        """Call a private function with signature fn(hGpu, params)."""
        fn_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        fn = ctypes.cast(self._fn(fid), fn_type)
        return fn(self.gpu, buf)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def make_buffer(size: int) -> ctypes.Array:
    buf = (ctypes.c_ubyte * size)()
    ctypes.memset(buf, 0, size)
    return buf


def set_u32(buf: ctypes.Array, offset: int, value: int) -> None:
    ctypes.cast(ctypes.byref(buf, offset), ctypes.POINTER(ctypes.c_uint32))[0] = value & 0xFFFFFFFF


def get_u32(buf: ctypes.Array, offset: int) -> int:
    return ctypes.cast(ctypes.byref(buf, offset), ctypes.POINTER(ctypes.c_uint32))[0]


def buf_to_bytes(buf: ctypes.Array) -> bytes:
    return bytes(buf)


def bytes_to_buf(data: bytes, size: int) -> ctypes.Array:
    if len(data) > size:
        raise ValueError("backup data too large")
    buf = make_buffer(size)
    ctypes.memmove(buf, data, len(data))
    return buf
