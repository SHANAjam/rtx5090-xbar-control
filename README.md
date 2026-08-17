# xbar5090

**Windows RTX 50-series XBAR / MSVDD / Propagation Ratio / V/F control via private NvAPI**

> 🌐 [中文说明](README.zh-CN.md) · 📖 [用户指南](docs/USER_GUIDE.md) · 🛠️ [开发者指南](docs/DEVELOPER_GUIDE.md) · 🐞 [调试指南](docs/DEBUGGING.md)

---

## ✨ 项目简介

本项目是一个 Windows 下的 RTX 50 系显卡 XBAR 控制工具，基于私有 NvAPI 实现：

- XBAR 频率偏移
- XBAR-domain MSVDD 偏移
- GPC→XBAR 传播比例
- XBAR V/F 点读写
- PERF limits 只读
- L2 数据完整性稳定性测试

> **上游来源**：Linux 侧工作来自 [LACT #1147](https://github.com/ilya-zlobintsev/LACT/issues/1147)（Loong0x00），Windows NvAPI 入口参考 [LACT PR #1158](https://github.com/ilya-zlobintsev/LACT/pull/1158)（Panchovix）。本项目是 Windows 移植/扩展。

---

## 🚀 快速开始（用户）

### 前置要求

1. **安装 mVolt+**（推荐 v0.32+）：https://github.com/b00nz/mVolt
2. **Windows 10/11 x64**
3. **RTX 50 系列显卡**（桌面或笔记本）
4. **管理员权限**

### 支持显卡

| 类型 | 型号 |
|---|---|
| 桌面 | RTX 5050 / 5060 / 5060 Ti (8GB/16GB) / 5070 / 5070 Ti / 5080 / 5090 / 5090 D / 5090 D v2 |
| 笔记本 | RTX 5050 / 5060 / 5070 / 5070 Ti / 5080 / 5090 Laptop GPU |

### 支持驱动

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

其他驱动请先运行 `probe` / `crack` 验证。

### 运行

```powershell
python run.py wizard
```

或右键 `xbar5090.exe` → 以管理员身份运行。

详细步骤见 [用户指南](docs/USER_GUIDE.md)。

---

## 🧑‍💻 开发者入口

- [开发者指南](docs/DEVELOPER_GUIDE.md) — 项目结构、逆向结论、驱动验证流程
- [技术笔记](docs/TECHNICAL_NOTES.md) — LACT #1147 / PR #1158 / issue #1159 / NVIDIA #1266 完整背景
- [逆向笔记](docs/REVERSE_NOTES.md) — GET_INFO 完整解码
- [发现清单](docs/FINDINGS.md) — 所有发现，已用/未用分类
- [驱动验证](docs/DRIVER_VALIDATION.md) — R572..R610 验证报告

---

## 🛠️ 常用命令

```powershell
python run.py status                 # 当前状态
python run.py status --json          # JSON 输出
python run.py vfp-status --json      # VF 状态 JSON
python run.py perf --json            # PERF JSON
python run.py wizard                 # 交互向导
python run.py set-xbar --freq-khz 205000 --msvdd-uv 10000 --yes
python run.py set-ratio --ratio 1.2 --yes
python run.py vfp-auto-range --msvdd-mv 1150 --freq-khz 88000 --yes
python run.py l2-test                # L2 稳定性测试
python run.py profile-save myprofile # 保存配置
python run.py profile-apply myprofile --yes
python run.py autostart-install      # 安装开机自启
python run.py autostart-remove       # 移除开机自启
```

---

## 📚 文档地图

| 文档 | 适合谁 |
|---|---|
| [用户指南](docs/USER_GUIDE.md) | 普通用户 |
| [调试指南](docs/DEBUGGING.md) | 遇到问题的用户 |
| [开发者指南](docs/DEVELOPER_GUIDE.md) | 开发者 |
| [技术笔记](docs/TECHNICAL_NOTES.md) | 想了解原理的人 |
| [逆向笔记](docs/REVERSE_NOTES.md) | 逆向研究者 |
| [发现清单](docs/FINDINGS.md) | 所有发现 |
| [驱动验证](docs/DRIVER_VALIDATION.md) | 驱动适配验证 |
| [测试记录](TESTING.md) | L2 测试结果 |

---

## 🐞 反馈 Bug

我们非常需要你的反馈！

- 打开 [Issues](https://github.com/SHANAjam/rtx5090-xbar-control/issues)
- 附上：
  - 显卡型号 / 驱动版本
  - `python run.py status --json`
  - `python run.py probe`
  - 日志文件（`--log-file debug.log`）
  - 复现步骤

---

## ⚠️ 安全声明

- 本项目会修改 GPU 时钟/电压状态，**风险自负**。
- 每次写入前会自动备份，写入后回读校验。
- 未知驱动上不要使用 `--force-driver`。
- 笔记本用户请特别注意散热和功耗限制。

---

## 📦 发布

最新 Release：https://github.com/SHANAjam/rtx5090-xbar-control/releases

包含：

- `xbar5090.exe` 单文件版
- 源码
- Release Notes

---

## 📄 License

MIT（干净重构部分）。逆向得到的布局是驱动特定信息，按现状提供。
