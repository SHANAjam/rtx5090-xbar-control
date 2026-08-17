# Changelog

## [0.2.1] - 2026-08-17

### Added
- RTX 50-series desktop + laptop support.
- Cross-version static validation (R572..R610).
- Fully decoded PropRels GET_INFO descriptor.
- Dynamic layout adaptation.
- JSON output for status, fp-status, perf.
- Profile save/apply/list.
- Logging infrastructure (--verbose, --quiet, --log-file).
- CUDA source for L2 checker (src/xbar5090/data/xbar_l2_check.cu).
- GitHub Actions CI.
- Unit tests.
- AI/search discoverability (llms.txt, CITATION.cff, GitHub Topics).

### Changed
- Safety values renamed to "author's card reference".
- Daily reference updated to XBAR +200 / MSVDD 0 mV / Ratio 1.2 / VF +88.
- GPU check now requires confirmation for unlisted RTX 50 models.
- L2 test block count auto-selects by GPU model.
- detect_xbar_bank uses a generic positive-offset window heuristic, with manual fallback in wizard.
- Autostart feature removed by design (users should apply profiles manually).

### Fixed
- Interactive main menu for double-click/right-click.
- Console stays open on failure.
- Wizard works without driver_profile.json on known GB202 layout via manual fallback.
- cmd_profile_apply now verifies readback.
- Crack no longer mutates module globals.
- Various documentation inconsistencies.

## [0.1.2] - 2026-08-17

- Initial Windows private NvAPI implementation.
- XBAR/MSVDD/ratio/VF controls.
- L2 stability test.
- Driver auto-crack/probe.
- Safety limits and backups.

## [0.1.1] - 2026-08-17

- Early fixes and wizard improvements.

## [0.1.0] - 2026-08-17

- First working prototype.
