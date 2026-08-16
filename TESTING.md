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

## Author's overclocking journey

1. Started by overclocking the **core** and **memory**.
2. Found the Bilibili videos, downloaded **mVolt+**.
3. Used mVolt+ to adjust **NVVDD**, **MSVDD**, and **XBAR**.
4. Observed the following before this tool:
   - Core: ~3090 MHz @ ~1.01 V
   - XBAR: capped around ~2885 MHz
   - MSVDD: target 1.15 V, but it dropped when XBAR offset was raised
   - Memory: 34 Gbps (locked)
   - TSE: core curve ~27000, +800 W power ~28500, +205 XBAR ~29600
5. Observed the **MSVDD inversion**: higher XBAR offset caused MSVDD to drop
   (e.g. +205 -> ~1126 mV, +300 -> ~1086 mV, +450 -> ~1031 mV), and XBAR
   stayed bottlenecked around ~2882 MHz.
6. Found the community warning (original Chinese):

   > 单16pin的夜神锁800w功耗，2975的稳定xbar，3k会l2-核心存在数据错误，小心点别太搞，太高的电压有问题，以及注意核心频率和xbar有一个默认的0.9的传播轨，3kxbar理论上要3330核心。可以改 https://github.com/ilya-zlobintsev/LACT/issues/1147 详细的看这个。传播比例可以改，以及小心sys和mclk因为电压太高导致的不稳定。

7. Read the related LACT issues/PRs (#1147, #3, #1158, #1159) and wrote this
   tool with AI assistance.
8. Test standard:
   - Data-error detection from the branch descriptions (L2 integrity).
   - High-load game test (recommended: 4K 异环).
   - Observe XBAR and MSVDD in the background to judge whether the tool is
     effective.
   - Then run game stability tests.
9. After using this tool:
   - XBAR +235 MHz, MSVDD +10 mV, ratio 1.2, VF 225..245 +88 MHz
   - Physical XBAR ~2970 MHz stable in game
   - MSVDD stable at ~1.15 V
   - 3000 MHz was unstable and crashed in game.

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
