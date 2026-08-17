# Windows NvAPI PropRels GET_INFO descriptor reverse-engineering notes

Target: decode the Windows NvAPI relationship descriptor `0x00010100` into
type/src/dst/bidir, matching the Linux LACT layout (type=3, src=GPC, dst=XBAR,
bidir=1).

## Files analyzed

- `C:\Windows\System32\nvapi64.dll`
- `C:\Windows\System32\DriverStore\FileRepository\nv_dispi.inf_amd64_6f3cfb7117944855\nvapi64_impl.dll` (610.62)
- `C:\Windows\System32\DriverStore\FileRepository\nv_dispi.inf_amd64_0373d825005116d0\nvapi64_impl.dll` (newer)

## Runtime observations

`PropRelsGetInfo` returns a buffer:

- offset 0x00: version `0x00015798`
- offset 0x04: count `15`
- offset 0x08: mask `0x3fff`
- offset 0x8EC: descriptor `0x00010100`
- offset 0x8F0: default ratio raw `0xE660`
- offset 0x8F4: `0x00011C79`

`PropRelsGetControl` returns a buffer with ratio at known offset `0x64 + 0x04`.

## Static disassembly progress

### PropRels wrappers (driver 610.62)

File offsets / RVAs:

| Function | File offset | RVA |
|---|---|---|
| GET_INFO wrapper | 0xE8AB6 | 0xE96B6 |
| GET_CONTROL wrapper | 0xE8BD6 | 0xE97D6 |
| SET_CONTROL wrapper | 0xE8D16 | 0xE9916 |

All three are thin wrappers:
1. Check a global initialized flag (`cmp dword ptr [rip+...], -1`)
2. Put the private NvAPI ID on the stack
3. Call lookup function `0x102F50` (RVA 0x102F50)
4. Indirect call through the returned function pointer

The actual implementation is reached through `jmp rax` at RVA `0x45C0A0`
(thunk) after the lookup returns.

### Lookup function 0x102F50

Partially disassembled. It appears to walk a linked list of function entries:

- `rdi = [rcx]` (object)
- `rax = [rdi+8]` (first entry)
- Each entry:
  - `[rax+0x19]` byte: valid flag?
  - `[rax+0x20]` dword: function ID
  - `[rax+0x10]` qword: next entry pointer
  - `[rax]` qword: function pointer
- It scans until the requested ID is found or list ends.

Need to fully disassemble `0x102F50` to know the exact return value semantics.

## Static data table

The private NvAPI IDs appear in a data table around file offset `0x4DF538`
(RVA `0x4E1538`?). The table appears to contain pairs of pointers/IDs but has
not yet been decoded.

## Next steps

1. Fully disassemble `0x102F50`.
2. Decode the data table at `0x4DF538`.
3. Resolve the actual GET_INFO implementation pointer.
4. Disassemble the real GET_INFO function and map buffer writes to structure
   fields.
5. Correlate descriptor `0x00010100` byte layout with type/src/dst/bidir.
6. Reduce hardcoding in `prop_rels.py` using the decoded layout.

## Later progress

- Corrected the static table layout. Both tables are 16-byte records:
  `{u64 ptr, u32 id, u32 pad}`. The tables start at file offsets:
  - `0x4DF530` (real implementations, full VAs)
  - `0x4E98C0` (NvAPI wrapper stubs, full VAs)
- For driver 610.88 (`nv_dispi.inf_amd64_0373d825005116d0`), the resolved
  mapping is:

  | NvAPI ID | Wrapper RVA | Real implementation RVA |
  |---|---|---|
  | `0xE826E4F0` (GET_INFO) | `0xE9730` | `0x213590` |
  | `0xCBFF71D0` (GET_CONTROL) | `0xE9850` | `0x212F20` |
  | `0xEF3D20EA` (SET_CONTROL) | `0xE9990` | `0x213CD0` |

- Full disassembly of GET_INFO `0x213590` shows it validates version
  `0x15798`, calls an RM helper, then copies relationship records into the
  user buffer starting at `0x8E8` with stride `0x150`.
- The descriptor bytes are written by a small dispatcher:
  - `0x202140` maps raw Linux relationship type `3..7` to Windows mapped
    type `0..4`.
  - Bytes at record `+4/+5/+6` are copied directly as
    `source / destination / bidirectional`.
- Frida was installed and tested, but in this sandboxed environment
  `Interceptor.attach` does not fire even for `kernel32!Sleep`, so dynamic
  instrumentation is unavailable here. Static analysis with capstone was
  sufficient to finish the decode.

## Decoded GET_INFO relationship record

Runtime verification on driver 610.88 (same as 610.62 layout):

```text
record base  : 0x8E8
record stride: 0x150
+0x00  u32  type (Windows mapped type; Linux raw type = type + 3)
+0x04  u8   source clock-domain index
+0x05  u8   destination clock-domain index
+0x06  u8   bidirectional flag
+0x07  u8   padding (zero)
+0x08  u32  ratio raw, U16.16
+0x0C  u32  inverse ratio raw, U16.16
```

Relationship 0 decodes as:

```text
Windows type = 0  -> Linux raw type = 3
src  = 0 (GPC)
dst  = 1 (XBAR)
bidir = 1
ratio_raw = 0xE660 (0.89990234375)
inverse_ratio_raw = 0x11C79 (1.111221)
```

The Windows descriptor u32 `0x00010100` is therefore:

```text
byte 0 = src  = 0x00
byte 1 = dst  = 0x01
byte 2 = bidir = 0x01
byte 3 = pad  = 0x00
```

## Status

- [x] Locate DLLs
- [x] Find private NvAPI IDs/versions in binary
- [x] Locate wrapper functions
- [x] Confirm wrappers use lookup function 0x102F50
- [x] Parse static ID/pointer table
- [x] Identify real-function candidates
- [x] Resolve actual GET_INFO implementation definitively
- [x] Decode descriptor type/src/dst/bidir
- [x] Reduce hardcoding in `prop_rels.py`

## Hard blocker

Dynamic instrumentation (Frida) is blocked in this sandbox, but static
analysis with capstone/pefile was sufficient to fully decode the GET_INFO
relationship descriptor on the validated 610.62/610.88 layout.
