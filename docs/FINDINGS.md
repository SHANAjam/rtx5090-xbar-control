# Findings Register

This file collects every meaningful discovery from the project, whether or not
it is currently used by the program. Items are grouped by status.

## A. Used by the program

### A.1 PropRels (GPC->XBAR propagation ratio)

- Private NvAPI IDs:
  - `0xE826E4F0` PropRelsGetInfo
  - `0xCBFF71D0` PropRelsGetControl
  - `0xEF3D20EA` PropRelsSetControl
- GET_INFO version `0x15798`; GET/SET_CONTROL version `0x1075C`.
- GET_INFO relationship records start at `+0x8E8`, stride `0x150`.
- Record fields:
  - `+0x00` u32 Windows mapped type (`0` = Linux raw type `3`)
  - `+0x04` u8 source domain (`0` = GPC)
  - `+0x05` u8 destination domain (`1` = XBAR)
  - `+0x06` u8 bidirectional flag
  - `+0x08` u32 ratio U16.16
  - `+0x0C` u32 inverse ratio U16.16
- Default ratio raw `0xE660` = `0.89990234375`.
- Descriptor `0x00010100` is `src=0, dst=1, bidir=1`, not a magic constant.

### A.2 ClkDomains (XBAR frequency / MSVDD offsets)

- Private NvAPI IDs:
  - `0xF58938F5` ClkDomainsGetControl
  - `0xD14B69CF` ClkDomainsSetControl
- V2 version `0x261A4`.
- Entry base `+0x124`, stride `0x304`.
- XBAR domain index `1`.
- Frequency offset at `entry + 0x114` (kHz).
- XBAR-domain MSVDD offset at `entry + 0x11C` (uV).

### A.3 V/F points

- Private NvAPI IDs:
  - `0x8895B510` VF_INFO
  - `0x7FEE9032` VF_STATUS
  - `0xDA025C3E` VF_GET_CONTROL
  - `0xFEC00D04` VF_SET_CONTROL
- Versions: INFO `0x78604`, STATUS `0x1E8604`, CTRL `0x474604`.
- STATUS records: base `+0x304`, stride `0x1E8`.
- CONTROL records: base `+0x304`, stride `0x424`.
- XBAR bank on validated GB202: flats `127..253`.
- CONTROL offset field at `record + 0x38` (mode 0, u32 kHz).

### A.4 Physical XBAR measurement

- `CLK_MEASURE_FREQ` `0x527FC458`, version `0x1000C`.
- Mask at `+4`, output at `+8`, XBAR mask `2`.
- Used for `status` physical XBAR readout.

### A.5 PERF limits

- `PERF_GET` `0xEFCEDD1F` is present and read-only.
- PERF limits SET is **not exposed** on the validated Windows drivers.

### A.6 L2 stability test

- Direct implementation of Loong0x00's "Minimal XBAR stability check".
- CUDA kernel: random L2 reads over 32 MiB, atomic mismatch counter.
- Integrated as `l2-test` and optional wizard step.

### A.7 Cross-version static validation

- NvAPI static table layout: `{u64 ptr, u32 id, u32 pad}`.
- Real-implementation table starts at `0x4DF530`; wrapper table at `0x4E98C0`
  (R610.88 DLL).
- Validated desktop RTX 50-series drivers R572.16 .. R610.88 all share the
  same IDs, versions, GET_INFO layout, ClkDomains offsets and VF offsets.
- Notebook drivers 572.83, 591.86, 610.62 were also validated and share the
  same layout (laptop writes remain disabled in the program).
- Scripts:
  - `scripts/validate_nvapi_drivers.py`
  - `scripts/derive_nvapi_offsets.py`
  - `scripts/run_full_validation.py`

### A.8 Dynamic layout adaptation (v0.2.1)

- PropRels validation now scans the GET_INFO buffer for the GPC->XBAR record
  instead of relying on hardcoded record offsets.
- ClkDomains entry base/stride are discovered live from the control buffer by
  finding the repeated entry header pattern.
- XBAR domain index is discovered from the control buffer when exactly one
  entry has a non-zero offset; otherwise it falls back to `driver_profile.json`
  or the NvAPI enum default (Xbar=1).
- VF STATUS/CONTROL record base/stride are discovered live from the returned
  buffers by finding the repeated type-0xD records.
- `detect_xbar_bank` falls back to `driver_profile.json` when the generic scan
  cannot identify the bank on a new card, so the bank is learned per machine
  rather than hardcoded in code.

## B. Discovered but not directly used

### B.1 Full disassembly / reverse-engineering artifacts

- `docs/lookup_102f50_disasm.txt`
- `docs/get_info_real_disasm.txt`
- `docs/get_control_real_disasm.txt`
- `docs/set_control_real_disasm.txt`
- `docs/*_full_61088.txt`
- `docs/*_57216*.txt`
These are reference material for future driver branches, not loaded by the
program.

### B.2 Frida dynamic instrumentation

- Frida was installed and tested, but `Interceptor.attach` does not fire in
  this sandbox even for `kernel32!Sleep`.
- Not used; static capstone/pefile analysis was sufficient.

### B.3 Ghidra / x64dbg

- Ghidra download was started but not needed after capstone completed the
  decode.
- x64dbg is recommended for a human on a normal desktop, but not used here.

### B.4 Multiple GET_INFO type-0 records

- GET_INFO contains several type-0 records with the same `src=0,dst=1,bidir=1`
  and different ratio/inverse-ratio pairs (e.g. 0.8/1.25, 1.2/0.833, 1.5/0.667).
- The program currently uses relationship 0 (`0xE660`); the other entries are
  not written by the tool.

### B.5 30000 TSE / historical analysis

- A detailed analysis of what 30000 Time Spy Extreme means and RTX 50-series
  "heirloom" potential was produced for the user.
- It is user-facing context, not implemented as a feature.

### B.6 mVolt+ integration

- mVolt+ v0.32 was used for base voltage, NVVDD, and observation.
- This project does not modify or replace mVolt+ startup tasks.

## C. Blocked / unresolved

### C.1 Physical MSVDD direct read

- No verified direct NvAPI read path for physical MSVDD on Windows.
- The wizard asks the user to enter MSVDD manually.

### C.2 PERF limits SET

- Not exposed on validated drivers; no write path implemented.

### C.3 CLK_MEASURE_FREQ independent validation

- Works on the author's card/driver; needs validation on more cards/drivers
  before treating as universal.

## D. External sources / credits

- LACT issue #1147: Loong0x00's XBAR propagation ratio and L2 test.
- LACT PR #1158: Panchovix / adjustable XBAR clock domains (RM path).
- LACT issue #1159: related discussion.
- NVIDIA/open-gpu-kernel-modules#1266: finite memory-clock maximum affecting
  XBAR/SYS.
- mVolt+: https://github.com/b00nz/mVolt
