# HYDRA VRAM/Power-limit unlock research notes

> Status: research only. No code from HYDRA has been copied or merged into this
> project. HYDRA Pro appears to be closed-source/paid; these notes are for
> evaluating whether a similar feature can be implemented in xbar5090.

## What HYDRA is

- Developer: **1usmus**
- Latest update/change feed on GitHub:
  <https://github.com/1usmus/HYDRA_UPDATE>
- According to public coverage (2026-08), **HYDRA 2.3B Pro** adds support for
  NVIDIA RTX 50-series:
  - unlocks GDDR7 memory-clock limits to **36 Gbps** (from the usual 34 Gbps or
    lower on some models),
  - raises the power-limit adjustment range to **125%**,
  - works without flashing a modified VBIOS,
  - currently distributed as a paid "Pro" version.

## Why it is not directly mergeable

The GitHub `HYDRA_UPDATE` repository contains only:

- `HYDRA_CHANGELOG.txt`
- `HYDRA_UPDATE_INFO.txt`

It does **not** contain the HYDRA source code. The tool itself is closed-source.
Therefore we cannot copy the VRAM-unlock implementation directly into xbar5090.

## What would be needed to implement a similar feature

1. **Find the private NvAPI/RM command** used by HYDRA on Windows for:
   - memory-clock/PLL limit override,
   - power-limit override beyond the VBIOS default.
2. **Reverse-engineer the buffer layouts** for the relevant GET/SET control
   functions on the validated driver family (R572..R610), in the same way this
   project already did for XBAR/MSVDD/ratio/VF.
3. **Add read-only probe first**, then a backed-up/read-back SET with strict
   safety limits, and finally an L2/game stability validation.
4. **Handle driver-branch differences**; the current project already has a
   `probe`/`crack` mechanism that could be extended.

## Risks

- VRAM overclocking beyond the factory lock can cause data corruption, visual
  artifacts, or hardware damage even if the tool reports success.
- The power-limit and memory-limit controls are likely private RM/NvAPI
  interfaces and may be driver/VBIOS-specific.
- HYDRA Pro is paid; reverse-engineering its behavior for compatibility may
  raise legal/ToS questions. Independent probing of the NVIDIA driver is safer.

## Download / payment (as of 2026-08)

- Official update feed: <https://github.com/1usmus/HYDRA_UPDATE>
- Official discussion/payment thread is the Overclock.net "Official HYDRA (and
  HYDRA PRO) Thread"; the exact price/subscription method is behind the forum
  and was not scrapeable from this environment (WAF/Cloudflare).
- Public coverage states the RTX 50 VRAM/power unlock is in the **paid Pro**
  tier; there is no open-source implementation in the GitHub update repo.

## Feasibility for xbar5090

- XBAR was cracked because the private NvAPI/RM control for clock domains is
  exposed and reversible. A 36 Gbps memory unlock would need the same class of
  private control for the **memory clock/PLL limit** and/or **power-limit SET**.
- Current `perf_limits` module is read-only; the validated Windows driver did
  not expose the PERF SET command.
- A quick read-only dump of `clk_domains` on the author's RTX 5090 shows only
  the XBAR domain entry nonzero; the memory clock limit is not visible through
  the same simple offset path, so additional reverse engineering is required.
- Conclusion: technically the same methodology could be attempted, but it is a
  separate reverse-engineering project with higher risk. Do not expect a quick
  merge from HYDRA; it is closed-source and paid.

## Suggested next step

- Run HYDRA on the same system and capture which NvAPI/RM functions it calls
  (e.g. with API Monitor/x64dbg or by observing `nvapi64.dll` exports used).
- Compare those IDs against known RM command tables in
  `docs/reverse/` and `scripts/validate_nvapi_drivers.py`.
- If a stable read-only GET can be found, add it to `candidates.json` and
  extend `probe.py`/`crack.py` before attempting any SET.
