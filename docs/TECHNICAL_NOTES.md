# Technical Notes

These notes summarize the reverse-engineered Windows NvAPI interfaces used by
this project. They were validated on one RTX 5090 (GB202), driver 610.62,
Windows.

## Conclusions (short version)

- Windows NvAPI V2 works for XBAR/MSVDD and propagation ratio.
- The propagation ratio is effective only when V/F and voltage support it.
- A stable game configuration was found:
  `XBAR +235 / MSVDD +10 mV / ratio 1.2 / VF 225..245 +88 MHz`
  → ~2970 MHz stable.
- 3000 MHz was unstable.
- PERF limits SET was not found on the validated Windows driver.

## NvAPI IDs and versions

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
| PERF limits | SET | not found on validated driver | - |

## Key structure offsets (validated driver)

### ClkDomains V2

- Domain entries start at `+0x124`, stride `0x304`.
- XBAR is domain index 1.
- Frequency offset at `entry + 0x114` (kHz).
- XBAR-domain MSVDD offset at `entry + 0x11C` (uV).

### Propagation ratio

- Relationship 0 default raw `0xE660` (`0.89990234375`).
- Control entry base `+0x64`, ratio at `entry + 0x04`.

### V/F points

- XBAR bank on validated GB202: flat `127..253` (127 points).
- STATUS records: `+0x304 + flat * 0x1E8`.
- CONTROL records: `+0x304 + flat * 0x424`.
- XBAR record type: user type `0xD`, maps to internal type `0x11`.
- Frequency offset written at `record + 0x38` (mode 0, u32 kHz).

## Key findings

- The NvAPI V1 ClkDomains struct is broken (as PR #1158 said), but **V2 works**.
- The propagation ratio is effective on Windows, but only when V/F and voltage
  allow it.
- V/F STATUS can change without the physical clock following; always verify
  with a real workload.
- PERF limits SET (`0x2080E0AF`) was not found in `nvapi64.dll` or
  `nvapi64_impl.dll` on the validated driver.

## Environment detection

- Validated active flat range: `0..647` (648 points).
- If a machine does not match this, the wizard refuses to continue.
