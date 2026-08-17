RTX 5090 XBAR 超频教学：从 mVolt+ 对齐电压，到 xbar5090 工具实战

本文仅基于作者自己的 RTX 5090 和驱动 610.62 验证。新手请勿轻易尝试。本文内容未在其他电脑/系统/环境/硬件上测试。超频调压有风险，如果黑屏、蓝屏、不稳定，先重启恢复默认，后果自负。

一、前置：先完成核心 VF 曲线超频和显存超频

在碰 XBAR 之前，建议先把两件事做好：

1. 用 mVolt+ 或你熟悉的工具，把核心 VF 曲线超频调到基本稳定。
2. 把显存超频也调到基本稳定。

记录好你稳定时的核心频率、显存频率、MSVDD、NVVDD。后面的 XBAR 调试要在这个基础上做，不要一开始就混在一起改。

二、用 mVolt+ / HWiNFO64 / 游戏做 MSVDD 和 NVVDD 对齐，并超 XBAR

1. 打开 HWiNFO64，找到显卡传感器，主要看 MSVDD、NVVDD、XBAR 频率。

2. 打开 mVolt+，先做 MSVDD 和 NVVDD 对齐。mVolt+ 官方地址：https://github.com/b00nz/mVolt

对齐的意思是：让 MSVDD 和 NVVDD 在负载下保持你想要的配合关系，不要出现电压倒挂或异常偏低。先分别调整 MSVDD 和 NVVDD 的偏移，用 mVolt+ 右上角的 boost 测试和游戏观察，找到两者配合稳定的电压组合。这一步不要急着加 XBAR。

3. 对齐完成之后，再开始加 XBAR 偏移。

每次小步加，比如 30 到 50 MHz。点 mVolt+ 右上角的 boost 测试，看 XBAR 实际频率有没有上去，同时看 MSVDD 有没有异常。然后再跑游戏，确认稳定性。

4. 重点来了。

如果在超 XBAR 时发现 MSVDD 明显下降，不要继续用“加 XBAR 的同时加 MSVDD”这种简单方式硬顶。正确做法是停下来，用下面介绍的 xbar5090 工具来处理。这个工具就是为了解决这种电压倒挂和 XBAR 频率卡住的问题。

三、xbar5090 工具介绍

xbar5090 是一个 Windows 下的 RTX 5090 XBAR 辅助工具，通过私有 NvAPI 接口读写：

XBAR 频率偏移
XBAR 域 MSVDD 偏移
GPC 到 XBAR 传播比
127 点 XBAR V/F 曲线

它不修改 MSI Afterburner 配置文件，也不修改 mVolt+ 的配置。仓库地址：https://github.com/SHANAjam/rtx5090-xbar-control

为什么需要它？mVolt+ 已经能调 XBAR、MSVDD、NVVDD，但在作者这张验证卡上，单独用 mVolt+ 提高 XBAR 偏移会导致 MSVDD 倒挂，XBAR 卡在约 2882 MHz。xbar5090 补上了传播比控制、127 点 XBAR V/F 读写、MSVDD 补偿和交互式向导。

四、xbar5090 工具使用

1. 获取

从 Release 下载：

xbar5090.exe，单文件版。
xbar5090-windows-folder.zip，文件夹版。

也可以直接下载源码，用 Python 运行。

2. 运行

方式一，用 exe：

以管理员身份打开 PowerShell，进入 exe 所在目录，输入：

.\xbar5090.exe wizard

也可以直接右键 xbar5090.exe，选择以管理员身份运行，会直接打开向导。

方式二，用源码：

以管理员身份打开 PowerShell，进入项目目录，输入：

python run.py wizard

需要 Python 3.10 或更高版本。

3. 交互式向导

运行向导后，工具会：

自动检测你显卡上的 XBAR V/F bank。
让你输入当前物理 MSVDD，这个值从 mVolt+ 或 HWiNFO64 里读。
根据 MSVDD 自动选择一段较宽的 V/F 范围。
显示当前值和允许范围。
让你输入 XBAR 偏移、MSVDD 偏移、传播比、V/F 范围、V/F 偏移。
汇总后确认，然后自动备份、写入、读回校验。

4. 作者验证过的稳定组合，仅供参考

在作者的 RTX 5090 加驱动 610.62 上：

XBAR 偏移：235 MHz
MSVDD 偏移：10 mV
传播比：1.2
V/F 偏移：88 MHz，范围 225 到 245

游戏内大约 2970 MHz 稳定。再往上，比如 3000 MHz，在作者这张卡上不稳定。这不是保证值，你的卡可能需要不同的电压和频率。

5. 常用命令

查看当前状态：

python run.py status

打开交互式向导：

python run.py wizard

设置 XBAR 和 MSVDD：

python run.py set-xbar --freq-khz 235000 --msvdd-uv 10000

设置传播比：

python run.py set-ratio --ratio 1.2

查看 V/F 状态：

python run.py vfp-status

恢复默认：

python run.py reset

保存快照：

python run.py snapshot

恢复快照：

python run.py restore-snapshot --snapshot backups\snapshot_xxx.json

多 GPU 时选择显卡：

python run.py --gpu 0 status

6. 安全机制

写操作会自动检查驱动版本，当前只允许验证过的 610.62 系列。写之前会备份，写之后会读回校验，失败或读回不一致会自动回滚。

7. 建议使用 agent 辅助完成

如果你是新手，或者不想手动算参数，建议使用 agent 辅助完成。先运行 python run.py status，把输出贴给 AI agent，告诉它你的目标频率、当前物理 MSVDD、显卡型号和驱动版本，让它帮你生成下一步命令，或者帮你分析为什么不稳。AI agent 可以减少误操作，但最终风险仍然由你自己承担。

五、参考视频

B 站相关超频教学视频：

https://www.bilibili.com/video/BV1e8gV6xEZC
https://www.bilibili.com/video/BV1NQbk66EBL
https://www.bilibili.com/video/BV12egT6bEqM

六、最后提醒

新手请勿轻易尝试。
本文内容未在其他电脑/系统/环境/硬件上测试。
只在你自己的显卡、驱动、系统上小步验证。
每次写入前备份，写入后读回校验。
如果系统不稳定，先恢复默认或重启。

祝顺利，安全第一。

感谢

感谢这三个视频的两位 UP 主，以及刷新在评论区的 LumineKelly：

skywalkermibnasa（前两个视频）：
https://www.bilibili.com/video/BV1e8gV6xEZC
https://www.bilibili.com/video/BV1NQbk66EBL

妹抖控Maidkon（第三个视频）：
https://www.bilibili.com/video/BV12egT6bEqM

本文全程通过 DeepSeek V4 Flash 完成，经过作者简单校对，不保证正确性。请谨慎参考。
