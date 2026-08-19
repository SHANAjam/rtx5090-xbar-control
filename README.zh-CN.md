# xbar5090

> Windows RTX 50 系 XBAR / MSVDD / 传播比例 / V/F 控制（基于私有 NvAPI）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/SHANAjam/rtx5090-xbar-control/actions/workflows/ci.yml/badge.svg)](https://github.com/SHANAjam/rtx5090-xbar-control/actions/workflows/ci.yml)

**English**：[README.md](README.md)

**👨‍💻 开发者直达：** [技术说明 (中文)](docs/TECHNICAL_NOTES.zh-CN.md) · [Technical Notes (EN)](docs/TECHNICAL_NOTES.md)

---

## 目录

- [这是什么？](#这是什么)
- [前置要求](#前置要求)
- [支持硬件](#支持硬件)
- [快速开始](#快速开始)
- [常用命令](#常用命令)
- [建议起点](#建议起点)
- [反馈](#反馈)
- [开发者](#开发者)
- [安全](#安全)
- [发布](#发布)

---

## 这是什么？

一个 Windows 下的 RTX 50 系 XBAR（crossbar）控制工具：

- XBAR 频率偏移
- XBAR-domain MSVDD 偏移
- GPC→XBAR 传播比例
- XBAR V/F 点读写
- PERF limits（只读）
- L2 数据完整性稳定性测试

上游来源：[LACT #1147](https://github.com/ilya-zlobintsev/LACT/issues/1147) · [LACT PR #1158](https://github.com/ilya-zlobintsev/LACT/pull/1158)

---

## 前置要求

1. **mVolt+**（推荐 v0.32+）：https://github.com/b00nz/mVolt
2. **Windows 10/11 x64**
3. **RTX 50 系显卡**（桌面或笔记本）
4. **管理员权限**

> mVolt+ 不显示温度。开始前请先在 mVolt+ 中**同步 MSVDD 和 NVVDD**，让两者处于同一水平。

---

## 支持硬件

| 类型 | 型号 |
|---|---|
| 桌面 | RTX 5050 / 5060 / 5060 Ti (8GB/16GB) / 5070 / 5070 Ti / 5080 / 5090 / 5090 D / 5090 D v2 |
| 笔记本 | RTX 5050 / 5060 / 5070 / 5070 Ti / 5080 / 5090 Laptop GPU |

### 已验证驱动

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

其他驱动必须先通过 `probe` / `crack` 验证。

---

## 快速开始

```powershell
python run.py wizard
```

或右键 `xbar5090.exe` → **以管理员身份运行**。

详细步骤见技术文档：[English](docs/TECHNICAL_NOTES.md) / [中文](docs/TECHNICAL_NOTES.zh-CN.md)。

---

## 常用命令

```powershell
python run.py status
python run.py status --json
python run.py vfp-status --json
python run.py perf --json
python run.py wizard
python run.py set-xbar --freq-khz 200000 --msvdd-uv 0 --yes
python run.py set-ratio --ratio 1.2 --yes
python run.py vfp-auto-range --msvdd-mv 1150 --freq-khz 88000 --yes
python run.py l2-test
python run.py l2-test --mb 8   # 如果默认 32 MiB 的 L2 缓冲区分配失败时使用更小缓冲区
python run.py profile-save myprofile
python run.py profile-apply myprofile --yes
```

---

> **关于开机自启**：本工具刻意不提供开机自启功能。需要开机自动应用设置的用户，请先保存 profile（`profile-save`），再手动应用或自行创建计划任务。这是刻意的安全选择。

## 建议起点

这不是通用参数，只是给新手开始调校的起点：

```text
MSVDD  ：与 NVVDD 同步（同一水平）
Ratio  ：1.2
XBAR   ：从 +200 MHz 开始试
VF     ：从 +88 MHz 开始试（每张卡单独调）
```

- `VF +88 MHz` 表示给选中的 XBAR V/F 点额外加 88 MHz 频率偏移。
- **88 MHz 不是“保守值”**，只是作者机器上的起点。
- 不同显卡 / VBIOS / 散热需要不同值。
- 想更保守可以从 **+44 MHz 或 0 MHz** 开始。
- 不稳定就先降低 XBAR。

---

## 反馈

遇到问题请到 [Issues](https://github.com/SHANAjam/rtx5090-xbar-control/issues) 反馈。

请附上：

- 显卡型号和驱动版本
- `python run.py status --json`
- `python run.py probe`
- 日志文件（`python run.py --verbose --log-file debug.log status`）
- 复现步骤

---

## 开发者

- [Technical Notes (EN)](docs/TECHNICAL_NOTES.md)
- [技术说明 (中文)](docs/TECHNICAL_NOTES.zh-CN.md)

---

## 安全

- 本工具会修改 GPU 时钟/电压，风险自负。
- 每次写入前自动备份，写入后回读校验。
- 自动验证失败时**不要**使用 `--force-driver`。
- 笔记本用户请特别注意散热和功耗限制。

---

## 发布

最新 Release：https://github.com/SHANAjam/rtx5090-xbar-control/releases

包含：

- `xbar5090.exe`
- 源码
- Release Notes

---

## AI / 引用

- 仓库根目录的 `llms.txt` 供 AI/搜索引擎抓取。
- 引用元数据：`CITATION.cff`。
- 欢迎引用或转载本项目，无需事先询问；如果方便，附上链接即可。

## License

MIT（干净重构部分）。逆向布局是驱动特定信息，按现状提供。
