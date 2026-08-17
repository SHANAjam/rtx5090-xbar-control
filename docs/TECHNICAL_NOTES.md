# Technical Notes

These notes summarize the reverse-engineered Windows NvAPI interfaces used by
this project. They were validated on one RTX 5090 (GB202), drivers 610.62 and
610.88, Windows. 610.88 was verified with `crack`/`probe`; the NvAPI layout is
the same as 610.62.

## Conclusions (short version)

- Windows NvAPI V2 works for XBAR/MSVDD and propagation ratio.
- The propagation ratio is effective only when V/F and voltage support it.
- On the validated RTX 5090 / driver 610.62/610.88, a stable game
  configuration was found:
  `XBAR +235 / MSVDD +10 mV / ratio 1.2 / VF auto wide range +88 MHz`
  (on the author's machine this resolves to 224..253)
  → ~2970 MHz stable.
- On that same configuration, 3000 MHz was unstable.
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
- `CLK_MEASURE_FREQ` (`0x527FC458`) is a newly found read path for physical
  XBAR frequency and **needs independent validation** on more cards/drivers.
- `PropRelsGetInfo` (`0xE826E4F0`) on the validated driver returns a
  relationship entry where the default ratio raw `0xE660` is immediately
  preceded by the descriptor `0x00010100`. This is used as a best-effort
  fingerprint check; other VBIOS may differ.

## L2 stability test

The bundled L2 data-integrity checker is a direct implementation of the
"Minimal XBAR stability check" published by **Loong0x00** in LACT issue #1147:

https://github.com/ilya-zlobintsev/LACT/issues/1147

The original PTX kernel uses `ld.global.cg.u32` random L2 reads over a 32 MiB
buffer, atomically counting mismatches. The project bundles this as
`l2-test` and the wizard can run it after applying settings. A crash during
the test means the current XBAR configuration is unstable; zero errors and no
new `nvlddmkm` events means it passes.

## Environment detection

- Validated active flat range: `0..647` (648 points).
- If a machine does not match this, the wizard refuses to continue.

## Driver adaptation

- `python run.py probe` verifies the known NvAPI layout read-only.
- `python run.py crack` auto-matches NvAPI IDs from `candidates.json`
  (read-only; only listed candidate IDs are called).
- Write commands accept `--force-driver` to skip the driver version check.
  This is dangerous and should only be used when the NvAPI layout is known to
  be compatible.

## Pitfalls

- NvAPI private calls use `fn(hGpu, params)`, not `fn(out, in)`.
- Wrong version headers cause `-9` / `-104` or hangs.
- SetControl requires administrator (`-137` otherwise).
- Successful SET + exact readback does **not** mean the physical clock follows.
- The propagation ratio is a request, not a direct clock setter.
- XBAR/VF requests can make MSVDD drop (inversion); MSVDD compensation is needed.
- V/F writes are coupled; a broad contiguous range is safer than single points.
- PERF limits SET was not found on the validated Windows driver.
- Brute-force probing private APIs can hang the GPU.
- Always back up before writing and verify readback after every write.
- On the validated RTX 5090 / driver 610.62, 3000 MHz was unstable and
  ~2970 MHz was the stable game result.
