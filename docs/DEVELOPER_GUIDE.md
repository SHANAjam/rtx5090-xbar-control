# 开发者指南

> 面向想理解、修改、扩展本项目的人。核心是逆向笔记、验证流程和代码结构。

## 1. 项目结构

```text
src/xbar5090/
  cli.py           # 命令行入口与命令分发
  nvapi.py         # NvAPI 加载与调用封装
  driver_check.py  # 驱动/GPU 支持检查
  clk_domains.py   # XBAR 频率/MSVDD 控制（动态布局）
  prop_rels.py     # GPC->XBAR 传播比例（动态记录发现）
  vf_points.py     # V/F 点读写（动态记录布局）
  perf_limits.py   # PERF limits 只读解析
  crack.py         # 驱动候选 ID 匹配
  probe.py         # 只读布局验证
  backup.py        # 备份/快照
  safety.py        # 安全边界
  l2test.py        # L2 稳定性测试
scripts/
  validate_nvapi_drivers.py   # NvAPI ID/版本/布局验证
  derive_nvapi_offsets.py     # Clk/VF 偏移推导
  run_full_validation.py      # 一键全量验证
  disasm_nvapi.py             # capstone 反汇编工具
docs/
  TECHNICAL_NOTES.md   # 技术结论 + LACT #1147 等背景
  REVERSE_NOTES.md     # GET_INFO 完整解码
  DRIVER_VALIDATION.md # 多驱动验证报告
  FINDINGS.md          # 所有发现（已用/未用）
  DEBUGGING.md         # 调试指南
  USER_GUIDE.md        # 用户指南
```

## 2. 核心逆向结论

### PropRels GET_INFO

- 记录起始 `+0x8E8`，步长 `0x150`（现已改为扫描发现）。
- 字段：
  - `+0x00` u32 类型（Windows 映射类型，Linux 原始类型 = +3）
  - `+0x04` u8 源域
  - `+0x05` u8 目标域
  - `+0x06` u8 双向标志
  - `+0x08` u32 比例 U16.16
  - `+0x0C` u32 逆比例
- 关系 0：`src=0 (GPC), dst=1 (XBAR), bidir=1, ratio=0xE660`。

### ClkDomains

- 版本 `0x261A4`。
- entry base/stride 动态发现，通常 `0x124 / 0x304`。
- 频率偏移 `+0x114`，MSVDD 偏移 `+0x11C`。

### V/F Points

- STATUS：base `0x304`，stride `0x1E8`。
- CONTROL：base `0x304`，stride `0x424`。
- 偏移字段 `+0x38`。
- XBAR bank 自动检测 + profile 回退。

## 3. 如何验证一个新驱动

1. 拿到驱动包里的 `nvapi64.dll` 或 `nvapi64_impl.dll`。
2. 运行：
   ```powershell
   python scripts/run_full_validation.py
   ```
   或对单个 DLL：
   ```powershell
   python scripts/validate_nvapi_drivers.py path\to\nvapi64.dll
   python scripts/derive_nvapi_offsets.py path\to\nvapi64.dll
   ```
3. 如果通过，把版本前缀加入 `driver_check.VALIDATED_DRIVER_PREFIXES`。
4. 如果没通过，需要重新逆向布局，并更新 `docs/REVERSE_NOTES.md`。

## 4. 如何添加新发现

- 所有发现统一记录在 `docs/FINDINGS.md`。
- 已使用的发现必须同时有代码实现和文档。
- 未使用的发现也保留，方便后人。

## 5. 调试

- 使用 `--verbose --log-file debug.log` 获取详细日志。
- 使用 `--json` 获取结构化输出。
- 如果怀疑 NvAPI 布局变化，先跑 `probe`，不要直接写。

## 6. 测试

```powershell
pip install -e .[dev]
pytest -q
```

CI 在 `.github/workflows/ci.yml` 中运行同样的测试。
