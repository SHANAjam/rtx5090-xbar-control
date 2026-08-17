# Technical Notes

> English technical documentation. Chinese version: [TECHNICAL_NOTES.zh-CN.md](TECHNICAL_NOTES.zh-CN.md)

## Table of Contents

- [1. Project structure](#1-project-structure)
- [2. NvAPI IDs and versions](#2-nvapi-ids-and-versions)
- [3. Reverse engineering findings](#3-reverse-engineering-findings)
  - [3.1 PropRels (GPC→XBAR propagation ratio)](#31-proprels-gpcxbar-propagation-ratio)
  - [3.2 ClkDomains (XBAR frequency / MSVDD)](#32-clkdomains-xbar-frequency--msvdd)
  - [3.3 V/F points](#33-vf-points)
  - [3.4 PERF limits](#34-perf-limits)
  - [3.5 L2 stability test](#35-l2-stability-test)
- [4. Dynamic layout adaptation](#4-dynamic-layout-adaptation)
- [5. Driver validation matrix](#5-driver-validation-matrix)
- [6. Debugging](#6-debugging)
- [7. Adding support for a new driver](#7-adding-support-for-a-new-driver)
- [8. References](#8-references)
- [9. Known limitations](#9-known-limitations)

## 1. Project structure

```text
src/xbar5090/
  cli.py           # CLI entry and command dispatch
  nvapi.py         # NvAPI loading and call wrapper
  driver_check.py  # GPU/driver support checks
  clk_domains.py   # XBAR frequency / MSVDD control
  prop_rels.py     # GPC->XBAR propagation ratio
  vf_points.py     # V/F point read/write
  perf_limits.py   # PERF limits read-only
  crack.py         # candidate ID matching
  probe.py         # read-only layout verification
  backup.py        # backup/snapshot helpers
  safety.py        # safety bounds
  l2test.py        # L2 stability test
scripts/
  validate_nvapi_drivers.py
  derive_nvapi_offsets.py
  run_full_validation.py
  disasm_nvapi.py
docs/
  TECHNICAL_NOTES.md
  TECHNICAL_NOTES.zh-CN.md
  reverse/          # disassembly artifacts
```

## 2. NvAPI IDs and versions

| Feature | Operation | NvAPI ID | Version |
|---|---|---|---|
| XBAR/MSVDD | GetControl | `0xF58938F5` | `0x000261A4` (V2) |
| XBAR/MSVDD | SetControl | `0xD14B69CF` | `0x000261A4` (V2) |
| Propagation ratio | GetInfo | `0xE826E4F0` | `0x00015798` |
| Propagation ratio | GetControl | `0xCBFF71D0` | `0x0001075C` |
| Propagation ratio | SetControl | `0xEF3D20EA` | `0x0001075C` |
| V/F points | INFO | `0x8895B510` | `0x00078604` |
| V/F points | STATUS | `0x7FEE9032` | `0x001E8604` |
| V/F points | GET_CONTROL | `0xDA025C3E` | `0x00474604` |
| V/F points | SET_CONTROL | `0xFEC00D04` | `0x00474604` |
| PERF limits | GET | `0xEFCEDD1F` | `0x0007388C` |
| PERF limits | SET | not found on validated drivers | - |
| Physical XBAR | CLK_MEASURE_FREQ | `0x527FC458` | `0x0001000C` |

## 3. Reverse engineering findings

### 3.1 PropRels (GPC→XBAR propagation ratio)

- GET_INFO records start at `+0x8E8`, stride `0x150` (the program now scans for them instead of hardcoding).
- Record fields:
  - `+0x00` u32 Windows mapped type (Linux raw type = value + 3)
  - `+0x04` u8 source domain
  - `+0x05` u8 destination domain
  - `+0x06` u8 bidirectional flag
  - `+0x08` u32 ratio U16.16
  - `+0x0C` u32 inverse ratio U16.16
- Relationship 0 on the author's RTX 5090:
  - `type = 3 (Linux)`, `src = 0 (GPC)`, `dst = 1 (XBAR)`, `bidir = 1`
  - `ratio_raw = 0xE660` (`0.89990234375`)

### 3.2 ClkDomains (XBAR frequency / MSVDD)

- Entry base/stride are discovered live (usually `0x124 / 0x304`).
- XBAR domain index is discovered from the live buffer when exactly one entry has a non-zero offset; otherwise it falls back to `driver_profile.json` or the API enum default (`1`).
- Frequency offset at `entry + 0x114` (kHz).
- MSVDD offset at `entry + 0x11C` (uV).

### 3.3 V/F points

- STATUS records: base `0x304`, stride `0x1E8`.
- CONTROL records: base `0x304`, stride `0x424`.
- The base/stride are discovered automatically from the returned buffers.
- CONTROL offset field at `record + 0x38`.
- XBAR bank is auto-detected; on the author's RTX 5090 it is flats `127..253`.

### 3.4 PERF limits

- `PERF_GET` is read-only.
- `PERF_GET` SET command was not exposed in the validated Windows drivers.
- `perf_limits.parse_entries()` parses all limit entries.

### 3.5 L2 stability test

- Direct implementation of Loong0x00's "Minimal XBAR stability check" from LACT #1147.
- Uses random L2 reads over a 32 MiB buffer and atomic mismatch counting.
- Integrated as `l2-test`.

## 4. Dynamic layout adaptation

The program no longer relies on per-card hardcoded layout for:

- PropRels XBAR record location (scans buffer).
- ClkDomains entry base/stride (discovers from repeated entry header).
- VF STATUS/CONTROL record base/stride (discovers from repeated type-0xD records).
- XBAR bank (generic scan + `driver_profile.json` fallback).
- XBAR domain index (live buffer discovery + profile/API fallback).

Remaining constants are NvAPI structure field offsets (e.g. `+0x114`, `+0x38`). They are API-structure-level and were verified across R572..R610.

## 5. Driver validation matrix

Validated driver versions (desktop and selected notebook):

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

Validation checks:

- NvAPI ID table presence
- Version headers
- GET_INFO record layout
- ClkDomains entry offsets
- VF STATUS/CONTROL offsets

Scripts:

```powershell
python scripts/run_full_validation.py
```

## 6. Debugging

```powershell
python run.py --verbose --log-file debug.log status
python run.py --verbose --log-file debug.log probe
```

JSON output:

```powershell
python run.py status --json
python run.py vfp-status --json
python run.py perf --json
```

If `probe` fails:

- Do **not** use `--force-driver`.
- Collect `probe` output and report it.

## 7. Adding support for a new driver

1. Obtain `nvapi64.dll` or `nvapi64_impl.dll` from the driver package.
2. Run:
   ```powershell
   python scripts/validate_nvapi_drivers.py path\to\nvapi64.dll
   python scripts/derive_nvapi_offsets.py path\to\nvapi64.dll
   ```
3. If all checks pass, add the version prefix to `driver_check.VALIDATED_DRIVER_PREFIXES`.
4. If a check fails, reverse-engineer the new layout and update this document.

## 8. References

- LACT issue #1147: https://github.com/ilya-zlobintsev/LACT/issues/1147
- LACT PR #1158: https://github.com/ilya-zlobintsev/LACT/pull/1158
- LACT issue #1159: https://github.com/ilya-zlobintsev/LACT/issues/1159
- NVIDIA/open-gpu-kernel-modules#1266: https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1266
- mVolt+: https://github.com/b00nz/mVolt

## 9. Known limitations

- Physical MSVDD direct read is not implemented.
- PERF limits SET is not exposed.
- `cli.py` is still large; a future refactor may split it.
- The program is Windows-only.
- The exe is unsigned; antivirus false positives are possible.
- VF offset values are per-card tuning parameters, not universal constants.
