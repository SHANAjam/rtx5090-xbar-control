# 用户指南

> 面向普通用户。如果你只是想安全地调整 RTX 50 系显卡的 XBAR，从这里开始。

## 1. 开始之前（重要前置）

本项目**不替代 mVolt+**，而是与 mVolt+ 配合使用。

- 请先安装 **mVolt+ v0.32**（或更新版本）。
- 本项目负责：
  - XBAR 频率偏移
  - XBAR-domain MSVDD 偏移
  - GPC→XBAR 传播比例
  - XBAR V/F 点读写
- mVolt+ 负责：
  - 基础电压/NVVDD 控制
  - 物理电压观察
  - 部分时钟监控

> 没有 mVolt+ 也可以运行本项目，但很多“物理 MSVDD / 电压观察”需要你从 mVolt+ 或 HWiNFO64 手动读取。

## 2. 支持的显卡与驱动

### 显卡

| 类型 | 型号 |
|---|---|
| 桌面 | RTX 5050 / 5060 / 5060 Ti (8GB/16GB) / 5070 / 5070 Ti / 5080 / 5090 / 5090 D / 5090 D v2 |
| 笔记本 | RTX 5050 / 5060 / 5070 / 5070 Ti / 5080 / 5090 Laptop GPU |

### 已验证驱动

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

- 使用这些版本时，程序会直接放行。
- 使用其他驱动时，程序会先运行 `crack` / `probe` 自动验证。
- 如果自动验证失败，**不要**使用 `--force-driver` 强行写入。
  - 意思是：自动验证失败说明当前驱动/显卡的 NvAPI 布局与已验证布局不一致。
  - 强行写入可能会写到错误的内存位置，导致时钟/电压异常甚至损坏硬件。
  - 正确做法是：把 `probe` 输出发到 Issues，等适配后再用。

## 3. 快速开始

### 3.1 从源码运行

```powershell
python run.py wizard
```

### 3.2 从 exe 运行

右键 `xbar5090.exe` → **以管理员身份运行**。

### 3.3 推荐首次操作

1. 先在 mVolt+ 中**同步 MSVDD 和 NVVDD**（让 MSVDD 与 NVVDD 保持同一水平）。
   - mVolt+ 不提供温度显示，这里不需要看温度。
2. 运行 `python run.py status` 查看当前状态。
3. 运行 `python run.py wizard`，按提示输入：
   - 当前物理 MSVDD（从 mVolt+ 读取）
   - XBAR 偏移（建议从 **+200** 开始）
   - MSVDD 偏移（先与 NVVDD 同步后的水平）
   - 比例（1.2）
   - VF 偏移（+88 MHz）
4. 应用后，程序会询问是否运行 L2 稳定性测试，建议选择“是”。

## 4. 建议起点（不是固定参数）

```text
MSVDD  ：拉到与 NVVDD 相同水平
Ratio  ：1.2
XBAR   ：从 +200 MHz 开始试
VF     ：+88 MHz
```

- 这不是“作者日常稳定档”，而是给新手的通用起点。
- 不同显卡/VBIOS/散热需要单独试。
- 如果崩溃，先降 XBAR（例如 +200 → +178 或 +150）。

## 5. 常用命令

```powershell
python run.py status                 # 查看状态
python run.py status --json          # JSON 输出
python run.py vfp-status --json      # VF 状态 JSON
python run.py wizard                 # 交互向导
python run.py set-xbar --freq-khz 205000 --msvdd-uv 10000 --yes
python run.py set-ratio --ratio 1.2 --yes
python run.py vfp-auto-range --msvdd-mv 1150 --freq-khz 88000 --yes
python run.py l2-test                # L2 稳定性测试
python run.py profile-save myprofile # 保存当前配置
python run.py profile-apply myprofile --yes
python run.py autostart-install      # 安装开机自启
```

## 6. 遇到问题？

请看 [调试指南](DEBUGGING.md)。

如果仍无法解决，请反馈 bug：

- 打开 [Issues](https://github.com/SHANAjam/rtx5090-xbar-control/issues)
- 附上：
  - 显卡型号
  - 驱动版本
  - `python run.py status --json` 输出
  - `python run.py probe` 输出
  - 日志文件（如果用了 `--log-file`）
  - 复现步骤

> 反馈 bug 是对本项目最大的帮助。谢谢！
