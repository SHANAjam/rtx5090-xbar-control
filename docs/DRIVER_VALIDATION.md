# Multi-driver static validation (RTX 50-series Game Ready)

Validated 2026-08-17 using `scripts/validate_nvapi_drivers.py` and
`scripts/derive_nvapi_offsets.py` against the downloaded Game Ready WHQL
packages in `D:\迅雷下载\1`.

The same Game Ready driver package is used for every desktop RTX 50-series
model. NVIDIA's lookup API reports identical driver lists for RTX 5090
(pfid 1066), RTX 5090 D (pfid 1067), and RTX 5090 D v2 (pfid 1092), as well as
for 5050/5060/5060 Ti/5070/5070 Ti/5080. Therefore validating the 8 driver
packages validates the DLL layout for the whole desktop RTX 50 family.

For each version we:

1. Located the private NvAPI static table entries for:
   - PropRels GET_INFO `0xE826E4F0`
   - PropRels GET_CONTROL `0xCBFF71D0`
   - PropRels SET_CONTROL `0xEF3D20EA`
   - ClkDomains GET/SET `0xF58938F5` / `0xD14B69CF`
   - VF INFO/STATUS/GET/SET `0x8895B510` / `0x7FEE9032` / `0xDA025C3E` / `0xFEC00D04`
   - PERF GET `0xEFCEDD1F`
2. Disassembled the real functions and verified version constants:
   - GET_INFO `0x15798`
   - GET_CONTROL `0x1075C`
   - SET_CONTROL `0x1075C`
   - CLK_GET `0x261A4`
   - VF_INFO `0x78604`, VF_STATUS `0x1E8604`, VF_GET/SET `0x474604`
3. Verified GET_INFO record layout markers:
   - record stride `0x150`
   - record base around `0x8E8` / `0x8F0`
4. Verified ClkDomains entry offsets:
   - entry base `0x124`, stride `0x304`
   - frequency offset `+0x114`, MSVDD offset `+0x11C`
5. Verified VF record offsets:
   - STATUS: base `0x304`, stride `0x1E8`, fields `+0x24/+0x58/+0x64/+0xF0`
   - CONTROL: base `0x304`, stride `0x424`, offset field `+0x38`

The derivation accepts both absolute-offset codegen (R596/R610) and
base+relative codegen (R572..R591); all versions match the same layout.

## Result: all 8 versions PASS

| Version | Release | DLL | PropRels | Clk/VF IDs | GET_INFO layout |
|---|---|---|---|---|---|
| 572.16 | 2025-01-30 | nvapi64.dll | ✅ | ✅ | ✅ |
| 576.02 | 2025-04-16 | nvapi64.dll | ✅ | ✅ | ✅ |
| 580.88 | 2025-07-31 | nvapi64.dll | ✅ | ✅ | ✅ |
| 581.42 | 2025-09-30 | nvapi64.dll | ✅ | ✅ | ✅ |
| 591.86 | 2026-01-27 | nvapi64.dll | ✅ | ✅ | ✅ |
| 596.49 | 2026-05-12 | nvapi64.dll | ✅ | ✅ | ✅ |
| 610.62 | 2026-06-16 | nvapi64_impl.dll | ✅ | ✅ | ✅ |
| 610.88 | 2026-07-28 | nvapi64_impl.dll | ✅ | ✅ | ✅ |

Note: static validation now also derives the ClkDomains and VF entry/record
offsets across the whole R572..R610 span, so the validated driver prefix list
in `driver_check.py` has been expanded to all eight versions. The existing
`crack`/`probe` path is still available as a runtime safety net, but it is no
longer required just to recognize these driver versions.

## Notebook driver validation (added 2026-08-17)

The following notebook driver packages were also validated with the same
scripts and all passed:

| Version | Type | DLL | Result |
|---|---|---|---|
| 572.83 | Notebook | nvapi64.dll | ✅ |
| 580.88 | Desktop (already in main set) | nvapi64.dll | ✅ |
| 591.86 | Notebook | nvapi64.dll | ✅ |
| 610.62 | Notebook | nvapi64_impl.dll | ✅ |

This confirms the notebook and desktop Game Ready packages expose the same
private NvAPI layout on the validated branches. Laptop RTX 50-series writes
are now allowed by the program (use with caution; laptop cooling/power limits
differ from desktop).

## 5090 D five-span selection

RTX 5090 D and 5090 D v2 use the exact same Game Ready driver packages as the
RTX 5090. A good five-span set for a 5090 D owner is:

| Version | Date | Purpose |
|---|---|---|
| 572.16 | 2025-01-30 | launch-era layout |
| 576.02 | 2025-04-16 | early R576 |
| 581.42 | 2025-09-30 | R581 |
| 591.86 | 2026-01-27 | R591 |
| 610.88 | 2026-07-28 | current/newest |

Direct links are identical to the RTX 5090 links listed in
`rtx5090_gameready_direct_links.txt`.
