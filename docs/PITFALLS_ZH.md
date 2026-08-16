# 踩坑记录与经验教训

本文记录我们在 Windows 上逆向和使用 RTX 5090 私有 NvAPI 接口时踩过的坑。
本文由 DeepSeek harness（AI 辅助软件工程会话）协助完成，目的是让后来者少走弯路。

## 1. NvAPI 私有函数调用约定

- 私有函数通过 `nvapi_QueryInterface(function_id)` 获取。
- 验证过的调用约定是 `fn(NvPhysicalGpuHandle hGpu, void *params)`，
  **不是** `fn(out, in)`。
- 签名错误会返回 `-9`/`-104`；如果继续乱试布局，可能导致驱动挂起。

## 2. 结构版本头很重要

- ClkDomains V2 版本头是 `0x000261A4`，不是 `0x10964`。
- PropRels 版本头是 `0x0001075C`。
- VF INFO/STATUS/CONTROL 版本头：
  - INFO `0x00078604`
  - STATUS `0x001E8604`
  - CONTROL `0x00474604`
- 版本头错误会返回 `-9`/`-104`。

## 3. `pe.get_data()` 需要 RVA，不是文件偏移

用 `pefile` 反汇编 `nvapi64_impl.dll` 时：

- `pe.get_data(rva, size)` 需要 RVA。
- 用 `section.VirtualAddress + (file_offset - section.PointerToRawData)` 转换。
- 直接传文件偏移会得到垃圾反汇编。

## 4. SetControl 需要管理员权限

- 非管理员调用返回 `-137`（`NVAPI_INVALID_USER_PRIVILEGE`）。
- 管理员调用返回 `0`。
- 所有写操作必须提权。

## 5. SET 成功 + 精确读回 ≠ 实际生效

- LACT #1159 的 PWR bank 反例是真的。
- 我们观察到 V/F STATUS“采纳”了值（effective frequency 变了），但物理时钟没变。
- 必须用物理频率测量和真实负载验证。

## 6. 传播比是“请求”，不是“直接频率设置器”

- `ratio 0.95 -> 1.2` 读回精确，但 XBAR 不动，因为 V/F 或 MSVDD 才是瓶颈。
- 只有 V/F 簇 + MSVDD 补偿 + 传播比组合起来，物理 XBAR 才真正提升。

## 7. XBAR/VF 请求会触发 MSVDD 倒挂

- 这张卡上，提高 XBAR 频率请求会让调度器**压低 MSVDD**（例如 1150 -> 1140/1126/1031）。
- 加一点 ClkDomains MSVDD 偏移（+10mV）可以抵消，让 MSVDD 稳定在 1.15V。
- 不加补偿时，功耗会掉约 50W，XBAR 也不提升。

## 8. V/F 簇写入有耦合

- 改单个 XBAR V/F 点是精确的。
- 一次性改全部 127 点会出现部分/量化采纳。
- 围绕工作电压的小范围簇比全 bank 写入更可靠。

## 9. mVolt+ 启动参数反直觉

- `mVolt+.exe --apply-startup-profile --start-in-tray` 会退出，退出码 2。
- `--apply-startup-profile --elevated` 是一次性应用，应用完退出（退出码 2 是正常的）。
- `--start-in-tray --elevated` 才会驻留托盘。
- 正确顺序：**先 apply（一次性），再 tray（驻留）**。
- 可能还存在被禁用的重复任务，用 `Get-ScheduledTask` 检查。

## 10. 已验证驱动上未暴露 PERF limits SET

- RM SET 命令 `0x2080E0AF` 在 `nvapi64.dll` 和 `nvapi64_impl.dll` 中都没找到。
- PERF GET（`0xEFCEDD1F`）存在，只读。
- 不要在这个驱动分支上浪费时间找 SET 的 NvAPI 包装。

## 11. 暴力试探私有 API 可能让 GPU 死机

- 我们因为对私有 GET 循环试版本/count，导致系统死机。
- 即使只读调用，布局错误也可能挂驱动。
- 必须先静态确认版本、buffer 大小、count 语义，再发起真实调用。

## 12. 备份与恢复纪律

- 每次写前保存完整 control buffer。
- 每次写后读回校验。
- 保留已知良好 VF 备份：`vfp_xbar_range_pre_20260816_202144.bin`（225..245 +88MHz）。
- 重启会复位所有运行时 RM 设置，包括 VF 写入。

## 13. 这张卡的物理 XBAR 上限

- 验证组合下，物理 XBAR 游戏重载约 2943 MHz，峰值约 2961 MHz。
- 扩大 V/F 簇没有继续提升。
- ratio 1.25 没有提升（其中一次配置错误还导致死机）。
- 距离 2975 的剩余差距更像是供电/VRM/硅片体质限制，而不是软件锁。
