# xbar5090

> Windows RTX 50-series XBAR / MSVDD / Propagation Ratio / V/F control via private NvAPI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/SHANAjam/rtx5090-xbar-control/actions/workflows/ci.yml/badge.svg)](https://github.com/SHANAjam/rtx5090-xbar-control/actions/workflows/ci.yml)

**中文版**：[README.zh-CN.md](README.zh-CN.md)

**👨‍💻 Developers, jump straight to:** [Technical Notes (EN)](docs/TECHNICAL_NOTES.md) · [技术说明 (中文)](docs/TECHNICAL_NOTES.zh-CN.md)

---

## Hall of Fame

**3DMark Time Spy Extreme Graphics Score: 30,331**  
Rank: **#86 (single GPU)** / **#95 (all)**  
GPU: NVIDIA GeForce RTX 5090 32 GB · CPU: AMD Ryzen 9 9950X3D2  
Result: [spy/65251803](http://www.3dmark.com/spy/65251803)

![3DMark Time Spy Extreme Graphics Hall of Fame](./docs/images/hall-of-fame-main.png)

*Additional screenshots: [1](./docs/images/hall-of-fame-1.png) · [2](./docs/images/hall-of-fame-2.png) · [3](./docs/images/hall-of-fame-3.png)*

---

## Table of Contents

- [What is this?](#what-is-this)
- [Prerequisites](#prerequisites)
- [Supported hardware](#supported-hardware)
- [Quick start](#quick-start)
- [Common commands](#common-commands)
- [Suggested starting point](#suggested-starting-point)
- [Feedback](#feedback)
- [For developers](#for-developers)
- [Safety](#safety)
- [Release](#release)

---

## What is this?

A Windows tool that controls the XBAR (crossbar) clock domain on RTX 50-series GPUs using private NvAPI:

- XBAR frequency offset
- XBAR-domain MSVDD offset
- GPC→XBAR propagation ratio
- XBAR V/F point read/write
- PERF limits (read-only)
- L2 data-integrity stability test

Upstream work: [LACT #1147](https://github.com/ilya-zlobintsev/LACT/issues/1147) · [LACT PR #1158](https://github.com/ilya-zlobintsev/LACT/pull/1158)

---

## Prerequisites

1. **mVolt+** (recommended v0.32+): https://github.com/b00nz/mVolt
2. **Windows 10/11 x64**
3. **RTX 50-series GPU** (desktop or laptop)
4. **Administrator privileges**

> mVolt+ does not show temperature. Before starting, sync **MSVDD** and **NVVDD** in mVolt+ so they are at the same level.

---

## Supported hardware

| Type | Models |
|---|---|
| Desktop | RTX 5050, 5060, 5060 Ti (8GB/16GB), 5070, 5070 Ti, 5080, 5090, 5090 D, 5090 D v2 |
| Laptop | RTX 5050, 5060, 5070, 5070 Ti, 5080, 5090 Laptop GPU |

### Validated drivers

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

Other drivers must pass `probe` / `crack` first.

---

## Quick start

```powershell
python run.py wizard
```

Or right-click `xbar5090.exe` → **Run as administrator**.

For detailed steps, see the technical docs: [English](docs/TECHNICAL_NOTES.md) / [中文](docs/TECHNICAL_NOTES.zh-CN.md).

---

## Common commands

```powershell
python run.py status
python run.py status --json
python run.py vfp-status --json
python run.py perf --json
python run.py wizard
python run.py set-xbar --freq-khz 200000 --msvdd-uv 0 --yes
python run.py set-ratio --ratio 1.2 --yes
python run.py vfp-auto-range --msvdd-mv 1150 --freq-khz 88000 --yes
python run.py l2-test
python run.py l2-test --mb 8   # if the default 32 MiB checker buffer cannot be allocated
python run.py profile-save myprofile
python run.py profile-apply myprofile --yes
```

---

> **Note on autostart**: This tool intentionally does not include an
> autostart feature. Users who want settings applied at boot should save a
> profile (`profile-save`) and apply it manually or via their own scheduled
> task. This is a deliberate safety choice.

## Suggested starting point

This is **not** a universal setting. It is only a starting point for tuning your own card.

```text
MSVDD  : sync with NVVDD (same level)
Ratio  : 1.2
XBAR   : start at +200 MHz
VF     : start at +88 MHz (tune per card)
```

- `VF +88 MHz` means adding an 88 MHz frequency offset to the selected XBAR V/F points.
- **88 MHz is not a "conservative" value.** It was a starting point on the author's card.
- Different cards / VBIOS / cooling may need different values.
- If you want to be more conservative, start with **+44 MHz or 0 MHz**.
- If unstable, lower XBAR first.

---

## Feedback

Found a bug? Please open an [Issue](https://github.com/SHANAjam/rtx5090-xbar-control/issues).

Include:

- GPU model and driver version
- `python run.py status --json`
- `python run.py probe`
- Log file (`python run.py --verbose --log-file debug.log status`)
- Steps to reproduce

---

## For developers

- [Technical Notes (EN)](docs/TECHNICAL_NOTES.md)
- [技术说明 (中文)](docs/TECHNICAL_NOTES.zh-CN.md)

---

## Safety

- This tool modifies GPU clocks/voltages. Use at your own risk.
- Writes are backed up and read back before/after.
- Do **not** use `--force-driver` when auto-validation fails.
- Laptop users should pay extra attention to cooling and power limits.

---

## Release

Latest release: https://github.com/SHANAjam/rtx5090-xbar-control/releases

Includes:

- `xbar5090.exe`
- Source code
- Release notes

---

## AI / Citation

- `llms.txt` at the repo root is provided for AI/search crawlers.
- Citation metadata: `CITATION.cff`.
- You may reference or repost this project without asking; a link back is appreciated but not required.

## License

MIT (for the clean refactor). Reverse-engineered layouts are driver-specific and provided as-is.
