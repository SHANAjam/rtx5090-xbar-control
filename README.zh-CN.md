# xbar5090

**Windows RTX 5090：通过私有 NvAPI 提高可达到的 XBAR 频率**

> 🌐 [English](README.md)

> **AI 协助声明**：本项目由 AI 软件工程助手（DeepSeek）协助完成。作者不是专业开发者，不精通英文，代码和结论可能有错误。详见 [DISCLAIMER.md](DISCLAIMER.md)。

> **警告**：本项目会修改 GPU 时钟/电压状态，使用风险自负。每次写操作前请备份，写后请读回校验。

## 包含内容

- 私有 NvAPI 工具：
  - XBAR 频率偏移
  - XBAR 域 MSVDD 偏移
  - GPC→XBAR 传播比
  - 127 点 XBAR V/F 状态/控制
  - PERF limits 只读
- 测试结果和负载情况见 [TESTING.md](TESTING.md)

## 相比 mVolt+ 新增了什么

mVolt+ 可以设置 XBAR 偏移、MSVDD、NVVDD。但在这张验证卡上，单独提高 XBAR 偏移会导致 MSVDD 倒挂，XBAR 卡在约 2882 MHz。

本项目补上的是让 XBAR 偏移真正生效的部分：

- 传播比控制（0.9/1.2）
- 127 点 XBAR V/F 读写
- MSVDD 补偿（+10mV），避免倒挂
- 验证组合：`XBAR +235 / MSVDD +10mV / ratio 1.2 / VF 225..245 +88` → 游戏约 2970 MHz 稳定
- 开源 / 可脚本化 / AI 可调用

## 我们做了什么

- 逆向出 Windows 私有 NvAPI 接口：传播比、V/F 点、PERF limits（以及 XBAR/MSVDD 的可脚本化替代）。
- 写了小型 CLI 和交互式向导。
- 使用 **mVolt+ v0.32** 在 RTX 5090 / 驱动 610.62 上测试。
- A/B 测试后找到稳定配置（见 [TESTING.md](TESTING.md)）。
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
- 已验证驱动：**610.62** 和 **610.88**（610.88 已通过 `crack`/`probe` 验证，NvAPI 布局一致）
- 使用 mVolt+ v0.32 作为电压基础和时钟观察

## 下载

普通用户可以直接下载项目：

1. 打开本仓库。
2. 点击绿色 **Code** 按钮。
3. 点击 **Download ZIP**。
4. 解压后按使用说明操作。

如果没装 Python，可以用 **Releases** 里的预编译 exe（见下）。

## 预编译 exe

Releases 提供两个 Windows x64 版本：

- `xbar5090.exe` — 单文件版。
- `xbar5090-folder/` — 文件夹版（体积更大，通常启动更快，也更容易加入杀软白名单）。

请在**管理员**终端中运行，例如：

```powershell
xbar5090.exe wizard
```

也可以直接**右键 exe → 以管理员身份运行**，会直接打开交互式向导。两个版本内容与本仓库源码一致，请只从本仓库下载。

## 杀软误报提示

exe 使用 PyInstaller 打包，并且会调用私有 NvAPI 修改 GPU 时钟/电压。Windows SmartScreen 和很多杀毒软件可能把它报为可疑或误报。这是未签名且执行底层硬件写入的工具的常见情况。

如果你信任来源：

- 在 Windows 安全中心或杀毒软件中把下载的文件/文件夹加入排除项，或
- 改用 Python 运行源码（`python run.py wizard`）。

请只从本仓库下载，并与 Release 说明中的文件名/大小核对。

## 状态 / 未实现

- **CI / 单元测试**：当前不是优先事项。这是个人验证工具，不是生产软件。
- **代码签名**：未实现，所以可能出现杀软误报。
- **自动读取物理 MSVDD**：不承诺。NvAPI 直读物理 MSVDD 尚未验证；向导目前需要你手动输入 MSVDD。
- **Profile 系统 / JSON 输出**：实用但不紧急，尚未实现。

## 使用方法

普通用户请使用交互式向导（需要管理员）：

```powershell
python run.py wizard
```

它会显示当前值、可设置范围，并引导你逐步修改 XBAR 偏移、MSVDD 偏移、传播比和 V/F 点。

高级用户也可以使用直接命令，详见 [docs/USAGE.md](docs/USAGE.md)。

### CLI 直接交互 / AI 辅助交互范例

如果你喜欢直接命令行，或者想让 AI agent 帮你执行，以下是范例：

```powershell
# 读取当前状态
python run.py status

# 设置 XBAR 偏移 + MSVDD（管理员）
python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000

# 设置传播比（管理员）
python run.py set-ratio --ratio 1.2

# 设置 XBAR V/F 范围（管理员）
python run.py vfp-set-range --start 224 --end 253 --freq-khz 88000
```

所有写命令都支持 `--force-driver`，可跳过驱动版本检查：

```powershell
python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000 --force-driver
```

> **危险**：`--force-driver` 仅限明确知道 NvAPI 布局兼容的人使用。如果布局变了，写入可能损坏时钟/电压。

使用 AI 助手时，可以把 `status` 的输出贴给它，让它根据你的目标值生成正确的命令。

## mVolt+

本项目与 **mVolt+ v0.32** 一起测试。mVolt+ 用于：

- 调节 MSVDD 和 NVVDD，
- 调节 XBAR，
- 使用其自带的 boost 测试跑满 XBAR。

本项目**不替代 mVolt+**，而是在其之上增加额外的 XBAR/传播比/VF 控制。mVolt+ 官方仓库：https://github.com/b00nz/mVolt

## 观察说明

- **HWiNFO64**：可以直接查看 MSVDD 和 XBAR，也可以勾选“内存共享”，让 AI agent 帮你读取。
- **mVolt+ 右上角 boost 按钮**：低负载下点击会提升 XBAR 频率，方便查看最大频率。
- **开机自启**：本项目目前**没有实现开机自启**。如果需要，请让 AI 协助，或联系作者（我）。

## 驱动版本

验证过的驱动版本：**610.62** 和 **610.88**（Windows）。

更新驱动后运行：

```powershell
python run.py crack
```

`crack` 会从 `candidates.json` 中匹配新驱动的 NvAPI ID（只读探测）。匹配通过即可视为兼容。如果仍要在未验证驱动上写入，请在写命令后加 `--force-driver`。

## 跨版本兼容

私有 NvAPI 结构布局是驱动分支相关的。请使用：

- `python run.py probe` — 只读验证已知布局是否仍有效。
- `python run.py crack` — 只读自动匹配候选 ID。
- `--force-driver` — 跳过驱动检查（危险，仅限专家）。

如果值为 0 或报错，**不要写**，除非你完全了解风险。

## 参考链接

- 超频教学视频（B 站；详见视频内容、简介和评论区）：
  - https://www.bilibili.com/video/BV1e8gV6xEZC
  - https://www.bilibili.com/video/BV1NQbk66EBL
  - https://www.bilibili.com/video/BV12egT6bEqM
- mVolt+：https://github.com/b00nz/mVolt/
- Overclock.net RTX 5090 Owners Club：
  https://www.overclock.net/threads/official-nvidia-rtx-5090-owners-club.1814246/page-1974#replies

## License

MIT（针对整洁重构部分）。逆向布局仅适用于特定驱动，按现状提供。
