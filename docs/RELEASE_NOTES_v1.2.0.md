# xbar5090 v1.2.0 Release Notes

## New in v1.2.0

- **Desktop RTX 50-series family support**
  - RTX 5050, 5060, 5060 Ti, 5070, 5070 Ti, 5080, 5090, 5090 D, 5090 D v2.
- **Cross-version static validation (R572..R610)**
  - Validated driver prefixes:
    `572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88`.
  - NvAPI IDs, version headers, GET_INFO descriptor layout, ClkDomains entry
    offsets, and VF record offsets all verified.
- **Fully decoded PropRels GET_INFO descriptor**
  - Replaced the opaque `0x00010100` fingerprint with a field-level check:
    `type=0 (Linux 3) / src=0 (GPC) / dst=1 (XBAR) / bidir=1`.
- **New validation scripts**
  - `scripts/validate_nvapi_drivers.py`
  - `scripts/derive_nvapi_offsets.py`
  - `scripts/run_full_validation.py`
- **Documentation**
  - `docs/TECHNICAL_NOTES.md`: complete LACT #1147 / PR #1158 / issue #1159 /
    NVIDIA #1266 context.
  - `docs/FINDINGS.md`: all findings, used and unused, categorized.
  - `docs/REVERSE_NOTES.md`: full GET_INFO decode.
  - `docs/DRIVER_VALIDATION.md`: cross-version validation report.
  - README / README.zh-CN updated with doc map and supported hardware.

## Safety

- GPU check now accepts any **desktop RTX 50-series** card.
- Driver check still requires a validated prefix; unknown/new drivers must pass
  `crack`/`probe` or use `--force-driver`.
