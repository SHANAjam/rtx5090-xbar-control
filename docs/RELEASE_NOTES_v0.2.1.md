# xbar5090 v0.2.1 Release Notes

## New in v0.2.1

- **RTX 50-series family support (desktop + laptop)**
  - Desktop: RTX 5050, 5060, 5060 Ti (8GB/16GB), 5070, 5070 Ti, 5080, 5090, 5090 D, 5090 D v2.
  - Laptop: RTX 5050, 5060, 5070, 5070 Ti, 5080, 5090 Laptop GPU.
- **Cross-version static validation (R572..R610)**
  - Desktop and selected notebook drivers validated.
- **Fully decoded PropRels GET_INFO descriptor**
  - type/src/dst/bidir field-level validation instead of magic constant.
- **Dynamic layout adaptation**
  - PropRels XBAR record scan.
  - ClkDomains entry base/stride discovery.
  - VF STATUS/CONTROL record base/stride discovery.
  - XBAR bank fallback to `driver_profile.json`.
- **JSON output** for `status`, `vfp-status`, and `perf` (`--json`).
- **Write cooldown** between write commands.
- **Crack matching improvements** using dynamic read paths (globals removed).
- **Profile system**: `profile-save`, `profile-apply`, `profile-list`.
- **Autostart**: `autostart-install`, `autostart-remove`.
- **Logging infrastructure**: `--verbose`, `--quiet`, `--log-file`.
- **GitHub Actions CI**.
- **Unit tests** for safety and prop_rels.
- **Documentation restructure**:
  - `docs/USER_GUIDE.md`
  - `docs/DEVELOPER_GUIDE.md`
  - `docs/DEBUGGING.md`
  - README rewritten as a polished landing page with clear user/developer paths.
- **Documentation**
  - `docs/TECHNICAL_NOTES.md` with complete LACT #1147 / PR #1158 / issue #1159 / NVIDIA #1266 context.
  - `docs/FINDINGS.md`, `docs/DRIVER_VALIDATION.md`, `docs/REVERSE_NOTES.md`.
  - README / README.zh-CN updated with doc map and supported hardware.

## Safety

- GPU check accepts any RTX 50-series desktop or laptop.
- Driver check still requires a validated prefix; unknown/new drivers must pass
  `crack`/`probe` or use `--force-driver`.
- Laptop writes are allowed but should be used with extra caution due to
  different cooling/power limits.
