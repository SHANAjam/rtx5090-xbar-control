# Usage Guide (for RTX 5090 users)

This guide explains how to use the interactive wizard to change XBAR clock,
MSVDD voltage, propagation ratio, and V/F points on an RTX 5090.

> Warning: this modifies GPU clocks/voltages. Use at your own risk.

## Requirements

- Windows 10/11 x64
- RTX 5090 (GB202)
- Validated driver: 610.62 (other drivers may not work)
- Python 3.10+ installed
- Administrator PowerShell

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
2. Show current values and allowed ranges.
3. Let you enter new values (press Enter to keep current).
4. Show a summary and ask for confirmation.
5. Back up and apply after you confirm.

### What each value means

| Prompt | Meaning | Example |
|---|---|---|
| XBAR offset (MHz) | Extra XBAR clock offset | `235` = +235 MHz |
| MSVDD offset (mV) | Extra XBAR-domain voltage offset | `10` = +10 mV |
| Propagation ratio | GPC->XBAR ratio request | `1.2` |
| VF bank start/end | Which V/F points to change | detected on your machine |
| VF offset (MHz) | Extra frequency offset for those V/F points | `88` = +88 MHz |

### Known stable configuration (validated)

```text
XBAR offset  : 235 MHz
MSVDD offset : 10 mV
Ratio        : 1.2
VF offset    : 88 MHz (upper part of the detected bank)
```

This gave ~2970 MHz stable in game on the validated card.

### Reset to driver defaults

Enter:

```text
XBAR offset  : 0
MSVDD offset : 0
Ratio        : 0.9
VF offset    : 0
```

## Troubleshooting

- If `status` returns zeros or errors, your driver layout is not recognized.
  Do not write.
- If the wizard says it cannot detect the XBAR V/F bank, the GPU/driver is
  not recognized. Do not continue.
- If the system crashes, reboot; all runtime settings reset.

## Files

- `run.py` — entry point
- `src/xbar5090/` — core code
- `docs/TECHNICAL_NOTES.md` — technical details for analysis
