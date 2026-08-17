# 调试指南

> 遇到问题先看这里。请尽量提供日志和 JSON 输出。

## 1. 开启详细日志

```powershell
python run.py --verbose --log-file debug.log status
python run.py --verbose --log-file debug.log probe
python run.py --verbose --log-file debug.log wizard
```

- `--verbose`：输出 DEBUG 级别日志。
- `--quiet`：只显示错误。
- `--log-file`：把日志写入文件，方便反馈。

## 2. 常见问题

### 2.1 程序说“需要管理员”

所有写操作都需要管理员权限：

```powershell
# 右键 PowerShell → 以管理员身份运行
python run.py wizard
```

### 2.2 `probe` 失败

说明当前驱动/显卡布局与已验证布局不一致。

1. 先确认驱动版本是否在支持列表。
2. 运行 `python run.py crack` 尝试自动匹配。
3. 如果 crack 也失败，**不要**用 `--force-driver`。
   - `--force-driver` 会跳过布局验证；布局不匹配时可能写错位置，造成损坏。
4. 把 `probe` 输出发到 Issues。

### 2.3 L2 测试崩溃

L2 测试会真实压测 XBAR。崩溃说明当前 XBAR 频率不稳定：

- 降低 XBAR 偏移（例如 +205 → +178）。
- 检查 MSVDD 是否足够。
- 降低后重新跑 `l2-test`。

### 2.4 开机自启没生效

- 确认已用管理员运行 `autostart-install`。
- 查看任务计划程序里是否有 `xbar5090 Autostart`。
- 查看 `%TEMP%\xbar5090_autostart.log`。

### 2.5 杀软误报

- PyInstaller 打包 + 未签名 + 底层硬件写入，容易被误报。
- 如果信任源码，请添加排除项，或直接用 Python 运行。

## 3. 反馈 Bug 模板

```text
显卡型号：
驱动版本：
操作系统：
命令/操作：
预期结果：
实际结果：
```

并附上：

```powershell
python run.py status --json
python run.py probe
```

以及日志文件（如果有）。

反馈地址：https://github.com/SHANAjam/rtx5090-xbar-control/issues
