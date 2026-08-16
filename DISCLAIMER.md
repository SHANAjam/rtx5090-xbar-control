# Disclaimer / 免责声明

## English

This project was produced with the assistance of an AI software engineering
harness (DeepSeek). The human "developer" behind this repository:

- is not a professional software engineer,
- does not read or write English fluently,
- does not have formal GPU/driver reverse-engineering expertise,
- and may have made mistakes in the code, documentation, or conclusions.

The private NvAPI interface IDs, structure layouts, and RM command mappings
in this repository were reverse-engineered on a specific GPU/driver
combination. They may be wrong, incomplete, driver-branch-specific, or
harmful to your hardware.

**Use this software entirely at your own risk.**

- It can modify GPU clocks and voltages.
- It can crash your system.
- It can potentially damage hardware if misused.
- No warranty, express or implied, is provided.
- The author is not responsible for any loss, damage, or injury caused by
  using this project.

Before using any write command, back up your current settings and verify
readback after every change. Do not run this on hardware you cannot afford
to lose.

## 中文

本项目由 AI 软件工程助手（DeepSeek）协助完成。仓库背后的“开发者”：

- 不是专业软件工程师；
- 不精通英文；
- 不具备正式的 GPU/驱动逆向工程专业知识；
- 代码、文档或结论中可能存在错误。

本仓库中的私有 NvAPI 接口 ID、结构布局和 RM 命令映射是在特定显卡/驱动组合上逆向得到的，可能错误、不完整、仅适用于特定驱动分支，甚至可能损坏硬件。

**使用本项目完全自负风险。**

- 它会修改 GPU 时钟和电压；
- 可能导致系统崩溃；
- 如果使用不当可能损坏硬件；
- 不提供任何明示或暗示的担保；
- 作者不对任何损失、损坏或伤害负责。

使用任何写命令前，请备份当前设置，并在每次修改后验证读回。不要在不承担得起损失的硬件上运行。
