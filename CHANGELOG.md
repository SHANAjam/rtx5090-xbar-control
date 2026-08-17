# Changelog

All notable changes to this project are documented here.

## [0.2.1] - 2026-08-17

### Added
- Desktop RTX 50-series family support (5050..5090 D v2).
- Laptop RTX 50-series write support (no longer blocked).
- JSON output for `status` / `vfp-status` (`--json`).
- Write cooldown (1s between write commands).
- Basic unit tests in `tests/` (safety, prop_rels).
- Crack matching now uses dynamic layout read paths (less false-positive risk).
- XBAR domain index discovery from live control buffer (profile/API fallback).
- Unified user-facing stable combo to +205 / VF 224..253 (README, USAGE, wizard).
- Cross-version static validation for R572.16..R610.88 (desktop + selected notebook).
- Fully decoded PropRels GET_INFO descriptor (type/src/dst/bidir).
- Dynamic layout discovery:
  - PropRels XBAR record scan (no hardcoded record offsets).
  - ClkDomains entry base/stride discovery.
  - VF STATUS/CONTROL record base/stride discovery.
  - XBAR bank fallback to `driver_profile.json`.
- New validation scripts:
  - `scripts/validate_nvapi_drivers.py`
  - `scripts/derive_nvapi_offsets.py`
  - `scripts/run_full_validation.py`
- Documentation:
  - `docs/FINDINGS.md`
  - `docs/DRIVER_VALIDATION.md`
  - `docs/REVERSE_NOTES.md`
  - `docs/RELEASE_NOTES_v0.2.1.md`
  - `CHANGELOG.md`
- Tags/topics metadata in `pyproject.toml` and README.

### Changed
- `driver_check.py` now accepts any RTX 50-series desktop or laptop GPU.
- `driver_check.py` validated driver prefixes expanded to 8 versions.
- README/README.zh-CN updated to current daily stable +205.
- Wizard reference combo updated to +205 / VF 224..253.

## [0.1.2] - 2026-08-17 (previous)

- Initial Windows private NvAPI implementation.
- XBAR/MSVDD/ratio/VF controls.
- L2 stability test integration.
- Driver auto-crack/probe.
- Wizard with force-mode prompt.
- Safety limits and backups.

## [0.1.0] - 2026-08-17 (initial)

- First working prototype.
