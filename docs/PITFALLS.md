# Pitfalls and Lessons Learned

This document records the traps we hit while reverse-engineering and using
private NvAPI interfaces on Windows for the RTX 5090. It was produced with the
assistance of a DeepSeek harness (an AI-assisted software engineering
session). The goal is to save the next developer from repeating the same
mistakes.

## 1. NvAPI private call convention

- Private functions are obtained through `nvapi_QueryInterface(function_id)`.
- The validated convention is `fn(NvPhysicalGpuHandle hGpu, void *params)`,
  **not** `fn(out, in)`.
- Wrong signatures return `-9` or `-104` and can make the driver hang if you
  keep trying random layouts.

## 2. Structure versions matter

- ClkDomains V2 uses version `0x000261A4`, not `0x10964`.
- PropRels uses version `0x0001075C`.
- VF INFO/STATUS/CONTROL use version-sized headers:
  - INFO `0x00078604`
  - STATUS `0x001E8604`
  - CONTROL `0x00474604`
- Passing the wrong version can cause `-9` or `-104`.

## 3. `pe.get_data()` wants an RVA, not a file offset

When disassembling `nvapi64_impl.dll` with `pefile`:

- `pe.get_data(rva, size)` expects an RVA.
- Use `section.VirtualAddress + (file_offset - section.PointerToRawData)` to
  convert file offsets to RVAs.
- Using a file offset directly produces garbage disassembly.

## 4. SetControl requires elevation

- Non-elevated `SetControl` calls return `-137`
  (`NVAPI_INVALID_USER_PRIVILEGE`).
- Elevated calls return `0`.
- Always run write commands from an elevated process.

## 5. Successful SET + exact readback does NOT mean the setting is effective

- The PWR bank counterexample from LACT #1159 is real.
- We observed V/F STATUS "adopting" values (effective frequency changing) while
  the physical clock did not follow.
- Always verify with a physical clock measurement and a real workload.

## 6. Propagation ratio is a request, not a direct clock setter

- `ratio 0.95 -> 1.2` read back exactly, but XBAR did not move when V/F or
  MSVDD limits were the binding constraint.
- Only the combination of V/F cluster + MSVDD compensation + ratio moved the
  physical XBAR.

## 7. MSVDD "inversion" under XBAR/VF requests

- On this card, raising XBAR frequency requests can make the scheduler **drop**
  MSVDD (e.g., 1150 -> 1140/1126/1031).
- A small ClkDomains MSVDD offset (+10 mV) can compensate and hold MSVDD at
  1.15 V.
- Without compensation, power drops ~50 W and XBAR does not improve.

## 8. V/F cluster writes are coupled

- Changing one XBAR V/F point is exact.
- Changing all 127 points at once produces partial/quantized STATUS adoption.
- A small contiguous cluster around the operating voltage is more reliable
  than a full-bank write.

## 9. mVolt+ startup arguments are counterintuitive

- `mVolt+.exe --apply-startup-profile --start-in-tray` exits with code 2.
- `--apply-startup-profile --elevated` is a one-shot apply that exits with
  code 2 (expected).
- `--start-in-tray --elevated` stays resident.
- The correct startup sequence is: **apply first (one-shot), then tray**.
- A disabled duplicate task may exist; inspect with:
  `Get-ScheduledTask | Where-Object TaskName -like '*mVolt*'`.

## 10. PERF limits SET is not exposed on the validated Windows driver

- The RM SET command `0x2080E0AF` was **not found** in `nvapi64.dll` or
  `nvapi64_impl.dll`.
- PERF GET (`0xEFCEDD1F`) exists and is read-only.
- Do not waste time trying to find a NvAPI wrapper for the SET command on this
  branch.

## 11. Brute-force probing private APIs can hang the GPU

- We caused a full system hang by iterating versions/counts on a private GET.
- Even read-only calls can hang the driver if the layout is wrong.
- Always statically confirm version, buffer size, and count semantics before
  making a live call.

## 12. Backup and restore discipline

- Always save the full control buffer before any write.
- Verify readback after every write.
- Keep a known-good VF backup: `vfp_xbar_range_pre_20260816_202144.bin`
  (flats 225..245 at +88 MHz).
- Reboot resets all runtime RM settings, including VF writes.

## 13. Physical XBAR ceiling on the tested card

- With the proven combo, physical XBAR reached ~2943 MHz under game load and
  ~2961 MHz peak.
- Expanding the V/F cluster further did not improve it.
- Ratio 1.25 did not improve it (and one misconfigured attempt crashed).
- The remaining gap to 2975 appears to be a physical/VRM/silicon limit rather
  than a software lock.
