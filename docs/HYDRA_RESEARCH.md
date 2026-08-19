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

## How people reached 36 Gbps before Hydra

- **MSI Afterburner patched database**: Unwinder provided a modified
  `MSIAfterburner.dat` for Afterburner 4.6.6 Beta 5 that extends the memory
  overclock range by +3000 MHz, allowing GDDR7 up to 36 Gbps.
  - https://www.kitguru.net/components/graphic-cards/joao-silva/msi-afterburner-bypass-allows-you-to-overclock-gddr7-memory-on-rtx-50-gpus/
- **High-end VBIOS cross-flash**: cards such as ASUS ROG Matrix / MSI
  Lightning / Galax HOF ship with higher memory/power limits. Flashing those
  VBIOS onto other 5090s can unlock higher memory clocks, but requires
  compatible PCB/fan topology and voids warranty.

## ASUS ROG Astral black-air + Matrix vBIOS situation

- Matrix 800W vBIOS can be cross-flashed to ROG Astral, but the **black Astral**
  has a fan-control conflict: the fourth rear fan shares the same control line
  as the front-center fan. White Astral has a separate header.
- To run Matrix vBIOS on black Astral, a hardware mod is required: change the
  pull-down resistor to pull-up on the EEPROM `SI` signal pin on the PCB.
- Source: https://diy.zol.com.cn/1126/11266586.html
- If you cannot do that hardware mod, the safer paths are:
  1. Stay on Astral 800W VBIOS and raise core offset/voltage curve with
     Afterburner / GPU Tweak III.
  2. Use Hydra Pro if available (software-level power/memory unlock).
  3. Do not flash incompatible VBIOS; risk of fan failure / brick.

## Concrete clues for a possible self-implemented 36 Gbps unlock

From LACT issue #1159 (Linux, RTX 5090 / driver 610.57.04):

- Offset-capable clock domains include:
  - GPC domain 0
  - XBAR domain 1
  - SYS domain 2
  - **memory domain 4**, offset range **-1000..+5000 MHz**
- `CLK_MEASURE_FREQ` (`0x20809006`, 8 bytes) can measure physical MCLK.
- PERF limits V2 strict ranges:
  - memory max/min: `0x75` / `0x78`
  - RM GET: `0x2080a079`
  - RM SET: `0x2080e0af`
- Source: https://github.com/ilya-zlobintsev/LACT/issues/1159

This suggests a path:
1. Find the Windows NvAPI IDs corresponding to `CLK_DOMAINS_GET_INFO`,
   `CLK_DOMAINS_SET_CONTROL` for domain 4, and `PERF_GET/SET`.
2. Read-only probe domain 4 offsets and memory max/min.
3. If readback is stable, add a safe SET with backup/readback, then validate
   with L2/stability tests.

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
