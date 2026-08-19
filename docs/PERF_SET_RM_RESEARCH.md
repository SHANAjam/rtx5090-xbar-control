# PERF SET / RM 通道研究留底（持续更新）

> 状态：只读逆向 + 一次受控写测试（未生效）。所有 GPU 写入均需用户明确批准。
> 本文件记录 RTX 5090 上绕过 PState20 上限、尝试 36 Gbps 显存的研究进度。

## 目标

- 当前 PState20 路径上限：显存 34 Gbps（17001 MHz = 17001000 kHz）
- 目标：36 Gbps（18000 MHz = 18000000 kHz）
- PState20 V2 SET 写 base/max 被忽略，delta 被 cap 在 +3000 MHz

## 关键结论（截至当前）

1. **NvAPI 用户态存在直达内核 RM 的通道**
   - `nvapi64_impl.dll` 导入 `CreateFileA` / `DeviceIoControl`
   - 打开 `\\.\NvAdminDevice`
   - `DeviceIoControl(0x8de0004)` 获取 client handle
   - `DeviceIoControl(0x8de0008)` 发送 RM control
   - 载荷格式：`NVDA 头 + 内联 NVOS54 载荷`

2. **内核 PERF SET 命令存在**
   - 命令 ID：`0x2080e0af`
   - 命令表大小：`0x13c08`
   - handler：`nvlddmkm.sys` RVA `0x4cd9b0`
   - handler 只读取参数前 12 字节（三个 dword），调用内部函数 `0x326cc0`
   - `0x2080e0ae`（小 SET）也存在，handler RVA `0x371ed0`，大小 `0x474`

3. **直连 RM 写当前不可行**
   - 直接 LoadLibrary `nvapi64_impl.dll` 拿到的模块不是 NvAPI 实际运行的实例
   - NvAPI 使用运行时展开的私有代码（公开 `QueryInterface` 返回的指针不在任何已加载模块范围内）
   - 直接调用磁盘上 `nvapi64_impl.dll` 的内部 RM 函数，GET/SET 均返回 `0x23`（参数结构被拒），未到达真正内核 handler
   - 已尝试正确 `hObject=0xb2000000` 仍为 `0x23`，确认问题在“用错实例”，不是 SET 参数

4. **公开 NvAPI 只读 GET 可用**
   - NvAPI ID `0xefcedd1f`（函数 RVA `0x28c0e0`）
   - 子命令 `0x4480c` / `0x6642c` / `0x7388c` 可返回 245 项 perf 表
   - 显存上限条目：entry 194，字段 `+0x18` / `+0x44` = `17001000` kHz（34 Gbps）
   - 核心条目：entry 63 / 67 等，`+0x18` / `+0x44` = `3210000` kHz

## SET 12 字节头假设（未验证）

基于内核 `0x326cc0` 和 GET 表结构推测：

| 偏移 | 含义 | 显存 36 Gbps 示例 |
|---|---|---|
| `+0x00` | 类型/标志（匹配 `flags & 2`） | `2` |
| `+0x04` | 条目 RM ID | `208`（0xD0，显存） |
| `+0x08` | 新频率 kHz | `18000000` |

- 核心 RM ID 示例：`67`（0x43）
- 用户侧 key 与 RM ID 映射表见 `nvapi64_impl.dll` RVA `0x486350`

## 受控写测试记录

- 第一次尝试：hObject 传错（0x100 / 0x5c000003），返回 `0x23`，无状态变化
- 第二次尝试：hObject 用正确值 `0xb2000000`，仍返回 `0x23`，无状态变化
- 原因：直接加载的 `nvapi64_impl.dll` 不是 NvAPI 私有运行实例，RM 调用在入口被拒

## 公开 SET API（已修正，重要）

子代理静态分析 + 只读 GET 验证后确认：

- `0x55590bdb`（RVA `0x2806a0`）是 **GET**，版本 `0x100fc`，只发 `0x2080a0ab`，不写。
- 真正写 `0x2080e0ae` 的是 **SET**：
  - NvAPI ID：`0x375e26cc`
  - RVA：`0x281f80`
  - 版本：`0x2121c`
- 对应的 GET：
  - NvAPI ID：`0x139c77f6`
  - RVA：`0x27f5e0`
  - 版本：`0x2121c`

### `0x2121c` 表布局（已只读验证）

- `+0x00`：版本 `0x2121c`
- `+0x94`：`u32` bitmask（当前 `0x1ff`，bit0~bit8 有效）
- 每个 bit 的值槽起始 `+0x98`，步长 `0x44`
- 实测：
  - bit0 → `+0x98` = 307000
  - bit1 → `+0xdc` = 1455000
  - **bit2 → `+0x120` = 17001000（显存频率）**
- 写入显存 36 Gbps：把 `+0x120` 改为 `18000000`（`0x112A880`），bit2 已在 mask 中

### 安全写流程

1. 调用 GET `0x139c77f6` 填好整个 `0x2121c` buffer
2. 修改 `+0x120 = 18000000`
3. 调用 SET `0x375e26cc` 写回
4. 用 GET `0x139c77f6` 读回验证

### 写测试结果（已执行）

- 非管理员调用 SET 返回 `-137`（NVAPI_INVALID_USER_PRIVILEGE）
- 管理员下 SET 返回 `0x0`（成功）
- 但 GET 读回仍为 `17001000`，没有变成 `18000000`
- 降频诊断：SET 16000000 也返回 0，但 GET 仍 17001000，SET 完全没生效
- 传入 buffer 在 SET 后仍保留 16000000，说明驱动没有回写/接受

### 子代理进一步分析（SET 为什么 no-op）

- SET `0x375e26cc` 支持 `0x10048` 和 `0x2121c`
- `0x2121c` 分支会把以下字段拷贝进内部 buffer：
  - `+0x04` → internal `+0x40`（疑似域选择 mask）
  - `+0x08` → internal `+0x48`
  - `+0x0c` / `+0x0d` → internal `+0x50` / `+0x51`（疑似 clock type / apply 标志）
  - `+0x94` mask → internal `+0x374`
  - `+0x98 + n*0x44` 值槽 → internal `+0x378 + n*4`
  - `+0x918` qword → internal `+0x3c4`
  - `+0x91c + n*0x48` / `+0x920 + n*0x48` 扩展槽 → internal `+0x3c8 + n*8`
- 直接照抄 GET buffer 只改 `+0x120` 的问题：`+0x04`、`+0x0c`、`+0x0d` 仍是 GET 输出的“当前/只读”状态，驱动不认为这是一次真正的 set；扩展槽 `+0x9ac/+0x9b0` 也可能仍指向旧目标。

### 最可能正确的 SET 构造（待实测）

```text
version = 0x2121c
+0x04   = 0x4                 # 只选 bit2（memory）
+0x0c   = 2                   # 或 1（clock type）
+0x0d   = 1                   # 或 0（apply/commit 标志）
+0x94   = 0x4                 # mask 只含 bit2
+0x120  = 18000000            # 目标频率
+0x9ac  = 18000000            # 扩展槽 min/max
+0x9b0  = 18000000
```

然后调用 SET `0x375e26cc`，最后用 GET `0x139c77f6` 回读 `+0x120` 验证。

### 修正版实测结果

- GET 原始值：`+0x04=0`、`+0x0c=0`、`+0x0d=0`、`+0x94=0x1ff`、`+0x120=17001000`、`+0x9ac=0`、`+0x9b0=0`
- 把 `+0x04=4`、`+0x0c=2`、`+0x0d=1`、`+0x94=4`、`+0x120=18000000`、`+0x9ac/+0x9b0=18000000` 后 SET 返回 `-104`（`0xffffff98`），没有生效
- 说明 `+0x04/+0x0c/+0x0d/+0x94` 不能按子代理猜的那样随便改
- 下一步候选：保持 GET 原始控制字段（`+0x04=0,+0x0c=0,+0x0d=0,+0x94=0x1ff`），只补扩展槽 `+0x9ac/+0x9b0=18000000`，再试 SET

### 扩展槽实测结果

- 保持 GET 原始控制字段，只把 `+0x120/+0x9ac/+0x9b0` 设为 18000000
- SET 返回 `0x0`，但 GET 仍 17001000，扩展槽仍 0
- 结合之前 16000000 降频也不变，基本可以判定：**这个 SET 调用在当前驱动上不会真正写入该字段**
- 可能原因：
  1. 缺少额外的“提交/应用”步骤（另一个 NvAPI 调用）
  2. `0x2121c` 不是该 GPU 实际生效的 SET 结构
  3. 驱动对该字段只读/被锁定，SET 静默忽略

## 下一步

- [ ] 逆向 `0x55590bdb` 的 `0x100fc` buffer 布局，重点是找到显存 entry 194 / RM ID 208 对应的写入字段
- [ ] 若公开 SET 可用，构造安全 buffer：只改显存频率字段，其余保持当前值，走官方 API 写
- [ ] 验证写后 GET 是否变为 `18000000`
- [ ] 若失败，评估 hook NvAPI 私有实例或放弃该旁路

## 安全边界

- 任何写操作前必须向用户说明并获批准
- 已有 VBIOS/驱动/核显备份
- 出现黑屏/TDR 时通过核显或第二 GPU 恢复
