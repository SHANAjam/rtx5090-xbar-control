# 技术说明

> RTX 50 系 XBAR（crossbar）控制项目的中文技术文档。英文版：[TECHNICAL_NOTES.md](TECHNICAL_NOTES.md)

## 目录

- [1. 项目结构](#1-项目结构)
- [2. NvAPI ID 与版本](#2-nvapi-id-与版本)
- [3. 逆向结论](#3-逆向结论)
  - [3.1 PropRels（GPC→XBAR 传播比例）](#31-proprelsgpcxbar-传播比例)
  - [3.2 ClkDomains（XBAR 频率 / MSVDD）](#32-clkdomainsxbar-频率--msvdd)
  - [3.3 V/F 点](#33-vf-点)
  - [3.4 PERF limits](#34-perf-limits)
  - [3.5 L2 稳定性测试](#35-l2-稳定性测试)
- [4. 反汇编过程与产物](#4-反汇编过程与产物)
- [5. 动态布局适配](#5-动态布局适配)
- [6. 驱动验证矩阵](#6-驱动验证矩阵)
- [7. 调试](#7-调试)
- [8. 如何支持新驱动](#8-如何支持新驱动)
- [9. 参考链接](#9-参考链接)
- [10. 已知限制](#10-已知限制)

## 1. 项目结构

```text
src/xbar5090/
  cli.py           # CLI 入口与命令分发
  nvapi.py         # NvAPI 加载与调用封装
  driver_check.py  # 驱动/GPU 支持检查
  clk_domains.py   # XBAR 频率 / MSVDD 控制
  prop_rels.py     # GPC->XBAR 传播比例
  vf_points.py     # V/F 点读写
  perf_limits.py   # PERF limits 只读
  crack.py         # 候选 ID 匹配
  probe.py         # 只读布局验证
  backup.py        # 备份/快照
  safety.py        # 安全边界
  l2test.py        # L2 稳定性测试
scripts/
  validate_nvapi_drivers.py
  derive_nvapi_offsets.py
  run_full_validation.py
  disasm_nvapi.py
docs/
  TECHNICAL_NOTES.md
  TECHNICAL_NOTES.zh-CN.md
  reverse/          # 反汇编产物
```

## 2. NvAPI ID 与版本

| 功能 | 操作 | NvAPI ID | 版本 |
|---|---|---|---|
| XBAR/MSVDD | GetControl | `0xF58938F5` | `0x000261A4` (V2) |
| XBAR/MSVDD | SetControl | `0xD14B69CF` | `0x000261A4` (V2) |
| 传播比例 | GetInfo | `0xE826E4F0` | `0x00015798` |
| 传播比例 | GetControl | `0xCBFF71D0` | `0x0001075C` |
| 传播比例 | SetControl | `0xEF3D20EA` | `0x0001075C` |
| V/F 点 | INFO | `0x8895B510` | `0x00078604` |
| V/F 点 | STATUS | `0x7FEE9032` | `0x001E8604` |
| V/F 点 | GET_CONTROL | `0xDA025C3E` | `0x00474604` |
| V/F 点 | SET_CONTROL | `0xFEC00D04` | `0x00474604` |
| PERF limits | GET | `0xEFCEDD1F` | `0x0007388C` |
| PERF limits | SET | 已验证驱动未找到 | - |
| 物理 XBAR | CLK_MEASURE_FREQ | `0x527FC458` | `0x0001000C` |

## 3. 逆向结论

### 3.1 PropRels（GPC→XBAR 传播比例）

- GET_INFO 记录起始 `+0x8E8`，步长 `0x150`（程序现在改为扫描发现）。
- 字段：
  - `+0x00` u32 Windows 映射类型（Linux 原始类型 = 值 + 3）
  - `+0x04` u8 源域
  - `+0x05` u8 目标域
  - `+0x06` u8 双向标志
  - `+0x08` u32 比例 U16.16
  - `+0x0C` u32 逆比例
- 作者 RTX 5090 上的关系 0：
  - `type = 3 (Linux)`、`src = 0 (GPC)`、`dst = 1 (XBAR)`、`bidir = 1`
  - `ratio_raw = 0xE660`（`0.89990234375`）

### 3.2 ClkDomains（XBAR 频率 / MSVDD）

- entry base/stride 动态发现（通常 `0x124 / 0x304`）。
- XBAR domain index 会从 buffer 动态发现；无法发现时回退到 `driver_profile.json` 或 API 枚举默认值（`1`）。
- 频率偏移：`entry + 0x114`（kHz）。
- MSVDD 偏移：`entry + 0x11C`（uV）。

### 3.3 V/F 点

- STATUS：base `0x304`，stride `0x1E8`。
- CONTROL：base `0x304`，stride `0x424`。
- base/stride 会自动从返回 buffer 发现。
- CONTROL 偏移字段：`record + 0x38`。
- XBAR bank 自动检测；作者 RTX 5090 上是 `127..253`。

### 3.4 PERF limits

- `PERF_GET` 只读。
- 已验证 Windows 驱动未暴露 SET。
- `perf_limits.parse_entries()` 可解析全部条目。

### 3.5 L2 稳定性测试

- 直接实现 Loong0x00 在 LACT #1147 中的 “Minimal XBAR stability check”。
- 使用 32 MiB 缓冲区随机 L2 读取 + 原子错误计数。
- 集成命令：`l2-test`。

## 4. 反汇编过程与产物

反汇编过程通过以下内容记录：

- 静态表解析：`scripts/validate_nvapi_drivers.py`
- 偏移推导：`scripts/derive_nvapi_offsets.py`
- Capstone 反汇编工具：`scripts/disasm_nvapi.py`
- 原始反汇编产物：[`docs/reverse/`](reverse/)

关键步骤：

1. 定位 NvAPI 静态 ID 表（`{u64 ptr, u32 id, u32 pad}`）。
2. 解析 wrapper 与真实实现。
3. 反汇编真实函数并识别版本检查。
4. 将 buffer 写入映射到结构体字段。
5. 跨 R572..R610 交叉验证。

原始文件包括：

```text
docs/reverse/lookup_102f50_full_61088.txt
docs/reverse/get_info_real_full_61088.txt
docs/reverse/get_control_real_full_61088.txt
docs/reverse/set_control_real_full_61088.txt
docs/reverse/clk_get_61088.txt
docs/reverse/vf_status_61088.txt
docs/reverse/vf_get_61088.txt
docs/reverse/rtx5090_gameready_direct_links.txt
```

## 5. 动态布局适配

程序已不再依赖以下硬编码：

- PropRels XBAR 记录位置（扫描 buffer）
- ClkDomains entry base/stride（从重复 entry 头发现）
- VF STATUS/CONTROL record base/stride（从重复 0xD 记录发现）
- XBAR bank（通用扫描 + `driver_profile.json` 回退）
- XBAR domain index（buffer 发现 + profile/API 回退）

剩余常量是 NvAPI 结构体字段偏移（如 `+0x114`、`+0x38`），属于 API 结构定义，已在 R572..R610 验证一致。

## 6. 驱动验证矩阵

已验证驱动版本（桌面 + 部分笔记本）：

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

验证内容：

- NvAPI ID 表
- 版本头
- GET_INFO 记录布局
- ClkDomains entry 偏移
- VF STATUS/CONTROL 偏移

脚本：

```powershell
python scripts/run_full_validation.py
```

## 7. 调试

```powershell
python run.py --verbose --log-file debug.log status
python run.py --verbose --log-file debug.log probe
```

JSON 输出：

```powershell
python run.py status --json
python run.py vfp-status --json
python run.py perf --json
```

如果 `probe` 失败：

- **不要**使用 `--force-driver`。
- 收集 `probe` 输出并反馈。

## 8. 如何支持新驱动

1. 从驱动包获取 `nvapi64.dll` 或 `nvapi64_impl.dll`。
2. 运行：
   ```powershell
   python scripts/validate_nvapi_drivers.py 路径\nvapi64.dll
   python scripts/derive_nvapi_offsets.py 路径\nvapi64.dll
   ```
3. 全部通过后，把版本前缀加入 `driver_check.VALIDATED_DRIVER_PREFIXES`。
4. 如果有失败项，需要重新逆向布局并更新本文档。

## 9. 参考链接

- LACT issue #1147：https://github.com/ilya-zlobintsev/LACT/issues/1147
- LACT PR #1158：https://github.com/ilya-zlobintsev/LACT/pull/1158
- LACT issue #1159：https://github.com/ilya-zlobintsev/LACT/issues/1159
- NVIDIA/open-gpu-kernel-modules#1266：https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1266
- mVolt+：https://github.com/b00nz/mVolt

## 10. 已知限制

- 物理 MSVDD 直接读取未实现。
- PERF limits SET 未暴露。
- `cli.py` 仍然较大，未来可能拆分。
- 项目仅支持 Windows。
- exe 未签名，杀软可能误报。
- VF 偏移属于每张卡单独调参的值，不是通用常数。
