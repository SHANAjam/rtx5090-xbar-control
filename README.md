# xbar5090

**Windows RTX 5090: raise the achievable XBAR clock via private NvAPI**

> 🌐 [中文说明](README.zh-CN.md)

> **AI assistance disclosure**: This project was produced with the assistance
> of an AI software engineering harness (DeepSeek). The author is not a
> professional developer and does not speak English fluently. Code and
> conclusions may contain errors. See [DISCLAIMER.md](DISCLAIMER.md).

> **WARNING**: This modifies GPU clock/voltage state. Use at your own risk.
> Always back up and verify readback after every write.

## What is included

- Private NvAPI helpers for:
  - XBAR frequency offset
  - XBAR-domain MSVDD offset
  - GPC->XBAR propagation ratio
  - 127-point XBAR V/F status/control
  - PERF limits read-only
- Test results and load conditions in [TESTING.md](TESTING.md)

## What this adds (compared to mVolt+)

mVolt+ already supports XBAR offset, MSVDD, and NVVDD. This project does
**not** replace mVolt+. It adds:

| Feature | mVolt+ | This project |
|---|---|---|
| XBAR offset | yes | duplicate |
| MSVDD / NVVDD | yes | duplicate |
| Propagation ratio (0.9/1.2) | likely no | **added** |
| 127-point XBAR V/F read/write | likely no | **added** |
| Open source / scriptable / AI-callable | no (GUI) | **added** |
| Validated combo that avoids MSVDD inversion | manual trial | **added** |

## What was done

- Reverse-engineered private Windows NvAPI IDs for propagation ratio, V/F
  points, and PERF limits (and XBAR/MSVDD as a scriptable alternative).
- Built a small CLI + interactive wizard.
- Tested with **mVolt+ v0.32** on an RTX 5090 / driver 610.62.
- A/B tested the controls and found a stable configuration (see
  [TESTING.md](TESTING.md)).
- Confirmed the propagation ratio is effective only when V/F and voltage
  support it.
- Confirmed PERF limits SET is not exposed on the validated Windows driver.
- AI-assisted; may contain errors.

## Documents

- **Usage**: [docs/USAGE.md](docs/USAGE.md) — how RTX 5090 users can use the
  wizard.
- **Technical notes**: [docs/TECHNICAL_NOTES.md](docs/TECHNICAL_NOTES.md) —
  conclusions, NvAPI IDs, versions, and structure offsets for analysis.

## Hardware / driver

Validated only on:

- NVIDIA RTX 5090 (GB202)
- Windows 10/11 x64
- A specific driver branch (`nv_dispi.inf_amd64_6f3cfb7117944855`)
- mVolt+ v0.32 was used for voltage base and clock observation

## Download

Normal users can download the project directly:

1. Open this repository.
2. Click the green **Code** button.
3. Click **Download ZIP**.
4. Extract the ZIP and follow the usage instructions.

## Status / not implemented

- **Packaging as exe / CI / unit tests**: not a priority for this project.
  It is a personal validation tool, not production software.
- **Automatic physical MSVDD reading**: not promised. Direct NvAPI reading of
  physical MSVDD has not been verified yet. The wizard currently asks you to
  enter MSVDD manually.
- **Profile system / JSON output**: useful but not urgent. Not implemented yet.

## Usage

For normal users, use the interactive wizard (requires administrator):

```powershell
python run.py wizard
```

It shows current values, allowed ranges, and lets you change XBAR offset,
MSVDD offset, propagation ratio, and V/F points step by step.

Advanced users can also use the direct commands; see
[docs/USAGE.md](docs/USAGE.md).

### CLI / AI-assisted interaction examples

If you prefer direct CLI commands, or you want to let an AI agent run them
for you, here are examples:

```powershell
# Read current status
python run.py status

# Set XBAR offset + MSVDD (admin)
python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000

# Set propagation ratio (admin)
python run.py set-ratio --ratio 1.2

# Set XBAR V/F range (admin)
python run.py vfp-set-range --start 225 --end 245 --freq-khz 88000
```

When using an AI assistant, you can paste your `status` output to it and ask
it to generate the correct command for your target values.

## mVolt+

This project was tested together with **mVolt+ v0.32**. mVolt+ is used to:

- adjust MSVDD and NVVDD,
- adjust XBAR,
- and run its built-in boost test to load the XBAR.

This project does **not** replace mVolt+; it adds additional XBAR/ratio/VF
controls on top. Official mVolt+ repository: https://github.com/b00nz/mVolt

## Observation tips

- **HWiNFO64**: you can view MSVDD and XBAR directly, or enable shared memory
  so an AI agent can read them for you.
- **mVolt+ boost button**: clicking the boost button (top-right) under low
  load raises the XBAR frequency, making it easy to view the maximum
  frequency.
- **Auto-start**: this project does **not** implement auto-start at boot.
  If you need it, ask an AI assistant for help or contact the author.

## Driver version

Validated driver version: **610.62** on Windows.

Driver branch path:
`nv_dispi.inf_amd64_6f3cfb7117944855`

## Cross-version compatibility

**Not solved.** The private NvAPI structure layouts are driver-branch
specific. If you use a different driver:

- First run `python run.py status` to see whether XBAR/MSVDD/ratio read
  plausible values.
- If values are zero or the command returns an error, **do not write**.
- Re-verify the layouts for your driver before using write commands.

## References

- Overclocking tutorials (Bilibili; see video content, description, and comments):
  - https://www.bilibili.com/video/BV1e8gV6xEZC
  - https://www.bilibili.com/video/BV1NQbk66EBL
  - https://www.bilibili.com/video/BV12egT6bEqM
- mVolt+: https://github.com/b00nz/mVolt/
- Overclock.net RTX 5090 Owners Club:
  https://www.overclock.net/threads/official-nvidia-rtx-5090-owners-club.1814246/page-1974#replies

## License

MIT (for the clean refactor). Reverse-engineered layouts are driver-specific
and provided as-is.
