# nvlddmkm.sys PERF SET dispatch research (read-only)

> Status: read-only reverse engineering notes. No writes were performed while
> collecting this data. This documents where and how the kernel driver handles
> the RM `PERF SET` command (`0x2080e0af`).

## Analyzed file

```text
C:\Windows\System32\DriverStore\FileRepository\nv_dispi.inf_amd64_6f3cfb7117944855\nvlddmkm.sys
```

- Size: 120,295,656 bytes
- Image base: `0x140000000`
- Driver branch: 610.88 (matching the user's validated driver family)

## RM command occurrences

| Command | Meaning | Occurrences |
|---|---:|---:|
| `0x2080e0af` | PERF SET | 3 |
| `0x2080a079` | PERF GET | 2 |

Occurrence file offsets / RVAs:

```text
PERF SET:
  0x1572f7 -> RVA 0x157af7   (generic RM wrapper, code)
  0x2dafc9 -> RVA 0x2db7c9   (subdevice control dispatch, code)
  0xe718e0 -> RVA 0xe744e0   (.rdata table entry)

PERF GET:
  0x157087 -> RVA 0x157887   (generic RM wrapper, code)
  0xe70040 -> RVA 0xe72c40   (.rdata table entry)
```

## 1. Subdevice control dispatch

At `RVA 0x1402db7c7` there is a command dispatch switch:

```asm
cmp esi, 0x20810103
ja  short loc_1402DB7EF
je  short loc_1402DB7DF
cmp esi, 0x2080e0af        ; PERF SET
jne loc_1402DC560
mov rax, [rdi+0x150]       ; load handler pointer
jmp loc_1402DC592          ; jump to common call epilogue
```

Interpretation:

- `esi` = incoming RM command ID.
- `rdi` = subdevice/control object.
- `[rdi+0x150]` = function pointer selected for `0x2080e0af`.
- `loc_1402DC592` is the common indirect-call epilogue used by the dispatch.

This confirms the kernel has a **first-class PERF SET handler** wired into the
subdevice control path.

## 2. Generic RM wrapper

At `RVA 0x140157af5`, a wrapper function sets the RM command and calls a shared
transport:

```asm
mov rax, [r13+8]
mov r9d, 0x2080e0af        ; PERF SET command
mov r8d, [r14+4]           ; subdevice/status field
mov rcx, r13               ; device/control object
mov edx, [r14]             ; command/subdevice index
mov [rsp+0x28], 0x13c08    ; buffer size hint (0x13c08)
mov [rsp+0x20], rdi        ; output/input buffer
call qword ptr [rip+0xcaffa0]  ; indirect RM transport call
```

The same pattern exists for `0x2080a079` (PERF GET) at `RVA 0x140157887`.

Interpretation:

- This is a **generic RM command wrapper** inside the kernel.
- It can send both GET and SET RM commands through the same indirect call.
- The buffer size constant `0x13c08` matches the PERF limits control size used
  by the user-mode `perf_limits` module.

## 3. What this means for user mode

- `nvapi64_impl.dll` contains wrappers for `0x2080a079` (PERF GET) but **not**
  for `0x2080e0af` (PERF SET).
- The kernel driver contains both the dispatch and the generic RM wrapper for
  PERF SET.
- Therefore the missing link is **user-mode to kernel RM transport**, not the
  kernel handler itself.

Possible ways such a transport could exist:

1. A private NvAPI ID that wraps the generic RM call (not found in the
   analyzed `nvapi64_impl.dll`).
2. A direct kernel driver interface / IOCTL.
3. A signed third-party driver that reuses the RM call path.

## 4. Generic RM call target

The generic RM wrapper at `0x140157af5` calls through a function pointer stored
at `.rdata:0xe07ab8`, which resolves to `0x140cf1380`.

At `0x140cf1380` the code is a runtime thunk:

```asm
jmp rax
```

This means the actual RM transport is installed dynamically (likely patched at
driver load). It is not a simple static user-mode callable function.

## 5. User-mode to kernel gap

- `nvapi64.dll` and `nvapi64_impl.dll` do **not** import `DeviceIoControl` /
  `NtDeviceIoControlFile` in the analyzed driver branch.
- The user-mode PERF GET path therefore does not use an obvious standard IOCTL
  that we can trivially reuse for PERF SET.
- The PERF SET handler exists in `nvlddmkm.sys`, but no user-mode NvAPI entry
  point for it was found.

## 6. Safety boundary

- Writing to the kernel RM path requires either a custom kernel driver or an
  existing privileged interface.
- This is significantly more dangerous than user-mode NvAPI writes.
- Any implementation should be done with:
  - full driver/VBIOS backups,
  - a recovery path (iGPU/second GPU/dual BIOS),
  - small incremental changes,
  - monitoring for TDR/black screens.
