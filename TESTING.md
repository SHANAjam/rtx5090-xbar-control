# Testing Results and Load Conditions

> **Important**: All tests were performed using **mVolt+ v0.32** and the
> hardware configuration listed below. Results are specific to this GPU,
> driver branch, and cooling/power setup. They are **not** guaranteed on
> other cards or drivers.

## Hardware and software used

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 5090 (GB202, 10de:2b85, subsystem 1043:89e3) |
| VBIOS | 98.02.2E.40.85 |
| Driver version | 610.62 |
| Driver branch | validated `nvapi64_impl.dll` from `nv_dispi.inf_amd64_6f3cfb7117944855` |
| OS | Windows 10/11 x64 |
| Voltage/clock tool | **mVolt+ v0.32** (used to adjust MSVDD/NVVDD/XBAR and run its built-in boost XBAR test) |
| Our tools | private NvAPI scripts in this repository |
| Power limit | 800 W |
| Memory clock | 34 Gbps (locked) |

## Load conditions used

| Load | Description |
|---|---|
| mVolt+ built-in boost test | lightweight test inside mVolt+ (the tool referenced by the Bilibili UP) |
| GPU-Z Render Test | lightweight render load |
| Game load | 4K RT DLAA (the user's real workload) |

## Key results

### mVolt+ built-in boost test (XBAR +235 fixed)

| Combo | XBAR (MHz) | MSVDD |
|---|---:|---:|
| Baseline (no VF/MSVDD/ratio) | 2887 | 1.145 V |
| VF only | 2887 | 1.090 V |
| MSVDD only | 2880 | 1.150 V |
| Ratio only | 2910 | 1.150 V |
| VF + MSVDD | 2887 | 1.100 V |
| **VF + Ratio** | **3000** | 1.150 V |
| MSVDD + Ratio | 2880 | 1.150 V |
| VF + MSVDD + Ratio | 2970 | 1.150 V |

### Ratio A/B (XBAR +235, VF +88, MSVDD +10mV fixed)

| Ratio | XBAR (MHz) | MSVDD |
|---|---:|---:|
| 0.9 | 2887 | 1.100 V |
| 1.2 | 2970 | 1.150 V |

### XBAR offset steps (with VF +88, MSVDD +10mV, ratio 1.2)

| XBAR offset | Physical XBAR observed |
|---|---:|
| +205 MHz | ~2940 MHz (game) |
| +220 MHz | ~2955 MHz |
| +235 MHz | ~2970 MHz (stable in game) |
| +250 MHz | ~2985 MHz (crashed in game) |
| +257 MHz | ~3000 MHz (unstable; L2/crash risk) |

## Conclusions

- The propagation ratio is effective on Windows, but only when combined with
  V/F and voltage support.
- The stable game configuration found was:
  `XBAR +235 / VF 225..245 +88 / MSVDD +10mV / ratio 1.2` (~2970 MHz).
- 3000 MHz was reachable in mVolt+ boost test but **not stable** in game.
- mVolt+ was used for base voltage control and clock observation; our scripts
  were used for XBAR/VF/ratio writes.
