# xbar5090

**Windows RTX 50 系 XBAR / MSVDD / 传播比例 / V/F 控制（基于私有 NvAPI）**

> 🌐 [English](README.md) · 📖 [用户指南](docs/USER_GUIDE.md) · 🛠️ [开发者指南](docs/DEVELOPER_GUIDE.md) · 🐞 [调试指南](docs/DEBUGGING.md)

---

## ✨ 项目简介

- XBAR 频率偏移
- XBAR-domain MSVDD 偏移
- GPC→XBAR 传播比例
- XBAR V/F 点读写
- PERF limits 只读
- L2 稳定性测试

上游来源：[LACT #1147](https://github.com/ilya-zlobintsev/LACT/issues/1147) + [LACT PR #1158](https://github.com/ilya-zlobintsev/LACT/pull/1158)。

---

## 🚀 快速开始

### 前置

1. 安装 **mVolt+**：https://github.com/b00nz/mVolt
2. Windows 10/11 x64
3. RTX 50 系显卡（桌面/笔记本）
4. 管理员权限

### 支持显卡

桌面：5050 / 5060 / 5060 Ti (8/16GB) / 5070 / 5070 Ti / 5080 / 5090 / 5090 D / 5090 D v2  
笔记本：5050 / 5060 / 5070 / 5070 Ti / 5080 / 5090 Laptop GPU

### 支持驱动

```text
572.16, 576.02, 580.88, 581.42, 591.86, 596.49, 610.62, 610.88
```

### 运行

```powershell
python run.py wizard
```

或右键 `xbar5090.exe` → 以管理员身份运行。

详见 [用户指南](docs/USER_GUIDE.md)。

---

## 🧑‍💻 开发者

- [开发者指南](docs/DEVELOPER_GUIDE.md)
- [技术笔记](docs/TECHNICAL_NOTES.md)
- [逆向笔记](docs/REVERSE_NOTES.md)
- [发现清单](docs/FINDINGS.md)
- [驱动验证](docs/DRIVER_VALIDATION.md)

---

## 🛠️ 常用命令

```powershell
python run.py status --json
python run.py vfp-status --json
python run.py perf --json
python run.py wizard
python run.py l2-test
python run.py profile-save myprofile
python run.py profile-apply myprofile --yes
python run.py autostart-install
```

---

## 🐞 反馈 Bug

请到 [Issues](https://github.com/SHANAjam/rtx5090-xbar-control/issues)，附上：

- 显卡型号 / 驱动版本
- `status --json` 输出
- `probe` 输出
- 日志文件
- 复现步骤

---

## ⚠️ 安全

- 风险自负
- 每次写入自动备份 + 回读校验
- 未知驱动不要用 `--force-driver`
- 笔记本注意散热

---

## 📦 Release

https://github.com/SHANAjam/rtx5090-xbar-control/releases

---

## 📄 License

MIT（干净重构部分）。
