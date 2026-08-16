# xbar5090

**Windows RTX 5090：通过私有 NvAPI 提高可达到的 XBAR 频率**

> 🌐 [English](README.md)

> **AI 协助声明**：本项目由 AI 软件工程助手（DeepSeek）协助完成。作者不是专业开发者，不精通英文，代码和结论可能有错误。详见 [DISCLAIMER.md](DISCLAIMER.md)。

> **警告**：本项目会修改 GPU 时钟/电压状态，使用风险自负。每次写操作前请备份，写后请读回校验。

## 目标

在 Windows 上把 RTX 5090 物理可达到的 XBAR 频率从默认约 2885 MHz 提高到约 2970 MHz（稳定），通过 XBAR 偏移、MSVDD 偏移、传播比和 V/F 点调整的组合实现。

## 包含内容

- 私有 NvAPI 工具：
  - XBAR 频率偏移
  - XBAR 域 MSVDD 偏移
  - GPC→XBAR 传播比
  - 127 点 XBAR V/F 状态/控制
  - PERF limits 只读
- 测试结果和负载情况见 [TESTING.md](TESTING.md)
- 踩坑记录见 [docs/PITFALLS.md](docs/PITFALLS.md) 和 [docs/PITFALLS_ZH.md](docs/PITFALLS_ZH.md)

## 我们做了什么

- 逆向出 Windows 私有 NvAPI 接口：XBAR/MSVDD、传播比、V/F 点、PERF limits。
- 写了小型 CLI 来读写这些控制项。
- 使用 **mVolt+ v0.32** 在 RTX 5090 / 驱动 610.62 上测试。
- A/B 测试后找到稳定游戏配置：
  `XBAR +235 MHz / MSVDD +10 mV / ratio 1.2 / VF 225..245 +88 MHz`
  → 物理 XBAR 约 2970 MHz 稳定（3000 MHz 不稳定）。
- 确认传播比只有在 V/F 和电压配合时才生效。
- 确认验证过的 Windows 驱动未暴露 PERF limits SET。
- AI 协助完成，可能有错误。

## 文档

- **使用说明**：[docs/USAGE.md](docs/USAGE.md) — 5090 用户如何使用向导。
- **技术说明**：[docs/TECHNICAL_NOTES.md](docs/TECHNICAL_NOTES.md) — 结论、NvAPI ID、版本、结构偏移，供分析。

## 硬件/驱动

仅在以下环境验证：

- NVIDIA RTX 5090（GB202）
- Windows 10/11 x64
- 特定驱动分支（`nv_dispi.inf_amd64_6f3cfb7117944855`）
- 使用 mVolt+ v0.32 作为电压基础和时钟观察

## 使用方法

在项目根目录运行：

```powershell
# 状态
python run.py status

# 设置 XBAR 偏移 + MSVDD（管理员）
python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000

# 设置传播比（管理员）
python run.py set-ratio --ratio 1.2

# 设置 XBAR V/F 范围（管理员）
python run.py vfp-set-range --start 225 --end 245 --freq-khz 88000
```

写命令需要**管理员 PowerShell**。

## mVolt+

本项目与 **mVolt+ v0.32** 一起测试。mVolt+ 用于：

- 调节 MSVDD 和 NVVDD，
- 调节 XBAR，
- 使用其自带的 boost 测试跑满 XBAR。

本项目**不替代 mVolt+**，而是在其之上增加额外的 XBAR/传播比/VF 控制。mVolt+ 官方仓库：https://github.com/b00nz/mVolt

## 驱动版本

验证过的驱动版本：**610.62**（Windows）。

驱动分支路径：
`nv_dispi.inf_amd64_6f3cfb7117944855`

## 跨版本兼容

**未解决。** 私有 NvAPI 结构布局是驱动分支相关的。如果使用不同驱动：

- 先运行 `python run.py status`，确认 XBAR/MSVDD/ratio 是否读出合理值。
- 如果值为 0 或报错，**不要写**。
- 使用写命令前，请针对你的驱动重新验证布局。

## 找到的稳定配置

```text
XBAR +235 MHz
MSVDD +10 mV
传播比 1.2
V/F flats 225..245 +88 MHz
```

物理 XBAR：游戏内约 2970 MHz 稳定。

## License

MIT（针对整洁重构部分）。逆向布局仅适用于特定驱动，按现状提供。
