# Usage Guide (for RTX 5090 users)

This guide explains how to use the interactive wizard to change XBAR clock,
MSVDD voltage, propagation ratio, and V/F points on an RTX 5090.

> Warning: this modifies GPU clocks/voltages. Use at your own risk.

## Requirements

- Windows 10/11 x64
- RTX 5090 (GB202)
- Validated driver: 610.62 (other drivers may not work)
- Administrator PowerShell
- Python 3.10+ if running from source (not needed for prebuilt exe)

### No Python? Use the prebuilt executable

If you downloaded `xbar5090.exe` (single-file) or the
`xbar5090-folder` build, open an **administrator** terminal in that folder and
run:

```powershell
.\xbar5090.exe wizard
```

For the folder build:

```powershell
.\xbar5090-folder\xbar5090-folder.exe wizard
```

You can also just **right-click the exe → Run as administrator**; it starts
the wizard directly.

The rest of this guide is the same: replace `python run.py ...` with
`xbar5090.exe ...`.

## Step 1: Check Python

```powershell
python --version
```

If this does not show Python 3.10+, install Python from python.org and check
"Add Python to PATH".

## Step 2: Open the project folder

```powershell
cd C:\path\to\xbar5090
```

## Step 3: Read current status

```powershell
python run.py status
```

Example output:

```text
XBAR offset  : +0 MHz
MSVDD offset : +0.0 mV
Ratio        : 0.8999
```

If this fails or shows zeros, your GPU/driver may not be supported. Stop here.

## Step 4: Use the interactive wizard

Run as administrator:

```powershell
python run.py wizard
```

The wizard will:

1. Detect the XBAR V/F bank on your machine.
2. Ask you for the current physical MSVDD (mV) — read it from mVolt+ or
   HWiNFO.
3. Auto-select a broad V/F range around that MSVDD.
4. Show current values and allowed ranges.
5. Let you enter new values (press Enter to keep current).
6. Show a summary and ask for confirmation.
7. Back up and apply after you confirm.

### What each value means

| Prompt | Meaning | Example |
|---|---|---|
| Current physical MSVDD (mV) | The MSVDD voltage you are running at (read it from mVolt+/HWiNFO) | `1150` |
| XBAR offset (MHz) | Extra XBAR clock offset | `235` = +235 MHz |
| MSVDD offset (mV) | Extra XBAR-domain voltage offset | `10` = +10 mV |
| Propagation ratio | GPC->XBAR ratio request | `1.2` |
| VF bank start/end | Which V/F points to change; the wizard auto-selects a broad range around your MSVDD | e.g. `222..252` |
| VF offset (MHz) | Extra frequency offset for those V/F points | `88` = +88 MHz |

### Known stable configuration (validated)

```text
XBAR offset  : 235 MHz
MSVDD offset : 10 mV
Ratio        : 1.2
VF offset    : 88 MHz (upper part of the detected bank)
```

On the author's RTX 5090 with driver 610.62, this gave ~2970 MHz stable in
game.

### Reset to driver defaults

Enter:

```text
XBAR offset  : 0
MSVDD offset : 0
Ratio        : 0.9
VF offset    : 0
```

## Advanced commands

```powershell
# Reset everything to driver defaults (admin)
python run.py reset

# Save a full clk+prop+vf snapshot (read-only)
python run.py snapshot

# Restore a full snapshot (admin)
python run.py restore-snapshot --snapshot backups\snapshot_xxx.json

# Choose a GPU (default 0)
python run.py --gpu 0 status
python run.py --gpu 0 wizard
```

Write commands automatically:

- check the driver version (only 610.62 family is allowed),
- check value ranges,
- back up before writing,
- verify readback after writing,
- roll back if a write fails or readback mismatches.

## Troubleshooting

- If `status` returns zeros or errors, your driver layout is not recognized.
  Do not write.
- If the wizard says it cannot detect the XBAR V/F bank, the GPU/driver is
  not recognized. Do not continue.
- If the system crashes, reboot; all runtime settings reset.
- XBAR/VF requests can make MSVDD drop. If you see MSVDD falling, add a
  small MSVDD offset (e.g. +10 mV).
- On the author's RTX 5090 with driver 610.62, 3000 MHz was unstable in
  game. Do not assume higher is better.
- Always back up before writing; the wizard does this automatically.

## Files

- `run.py` — entry point
- `src/xbar5090/` — core code
- `docs/TECHNICAL_NOTES.md` — technical details for analysis
