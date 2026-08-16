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
- Pitfalls in [docs/PITFALLS.md](docs/PITFALLS.md) and
  [docs/PITFALLS_ZH.md](docs/PITFALLS_ZH.md)

## What was done

- Reverse-engineered private Windows NvAPI IDs for XBAR/MSVDD, propagation
  ratio, V/F points, and PERF limits.
- Built a small CLI to read/write these controls.
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

## Usage

From the project root:

```powershell
# Status
python run.py status

# Set XBAR offset + MSVDD (admin)
python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000

# Set propagation ratio (admin)
python run.py set-ratio --ratio 1.2

# Set XBAR V/F range (admin)
python run.py vfp-set-range --start 225 --end 245 --freq-khz 88000
```

Write commands require an **administrator** PowerShell.

## mVolt+

This project was tested together with **mVolt+ v0.32**. mVolt+ is used to:

- adjust MSVDD and NVVDD,
- adjust XBAR,
- and run its built-in boost test to load the XBAR.

This project does **not** replace mVolt+; it adds additional XBAR/ratio/VF
controls on top. Official mVolt+ repository: https://github.com/b00nz/mVolt

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

## License

MIT (for the clean refactor). Reverse-engineered layouts are driver-specific
and provided as-is.
