# 模拟阵列与 ADC 行为模型

> 刚学 Python 的你：本目录的 `.va` 不是 Python，也不是给 ISS 用的。
> 第一站请继续跑 `python scripts/sim/run_all.py`。公式对照见 `golden/mvm_ref.py` 的 `mvm_real()`。

这里的 Verilog-A 给 **Cadence Spectre / AMS** 用，不是 RTL 仿真的必选项。

## 先用哪条仿真路径？

| 阶段 | 工具 | 模型 | 你在学什么 |
|---|---|---|---|
| 第 1 天 | Python ISS | 整数黄金模型 | 固件、寄存器、中断 |
| 第 2 天 | Icarus / VCS | `mvm_array_digital.v` | 总线时序、FSM 延迟 |
| 第 3 天 | VCS / Xcelium | `tb/mixed/mvm_array_real.sv` | 电压/电导/电流量化 |
| 有 Virtuoso 时 | Spectre AMS | 本目录 `.va` | 真正的混合信号网表 |

题目允许「理想电流/电阻阵列 + 6-bit ADC 行为模型」。所以 **没有 AMS 也能交差**：用 SystemVerilog `real` 模型证明误差 ≤ 1 LSB，Verilog-A 作为选做加分。

## 物理约定（t28, 0.9 V）

```
x, w ∈ {0 … 63}
Vin = (x / 63) * 0.6 V          留出 0.3 V 余量，不顶到 0.9 V
G   = w * 1 µS
I_j = Σ Vin_i * G_ij
I_fs = 4 * 0.6 V * 63 µS = 151.2 µA
Vadc = I_j * R_T,  R_T ≈ 3.968 kΩ  → 满量程 0.6 V
code = round(Vadc / 0.6 * 63)
```

与数字侧 `y = (Σ x_i w_ij) / 252` 在理想情况下逐码相等。

## 在 Virtuoso 里怎么用

1. 每个 `.va` 建一个 Verilog-A cell，Check and Save。
2. 例化 4 个 `dac6`（输入向量）、1 个 `mvm_array_4x4`（把 w 参数绑到数字寄存器）、4 个 `adc6`。
3. 数字控制器的 `settle` / `adc` 计数对应 DAC 建立和 ADC 采样时钟。
4. AMS 仿真时：数字块用 `mvm_copro` 门级或 RTL，模拟块用本目录模型。

权重在 Verilog-A 里目前是 **parameter**，适合第一版网表。若要把 16 个 6-bit 码做成电气端口，按 `dac6` 的 code 引脚同样展开即可。

版图（数字 Innovus + 模拟 4×4 电阻阵列怎么画、资料从哪找）见 **`docs/mvm_layout_tutorial.md`**。

## 参考

- AnalogHub Verilog-A ADC/DAC：https://analoghub.ie/category/verilogModels/article/ADC
- DVCON *SystemVerilog Real Models for an In-Memory Compute Design*
- PicoSoC / PicoRV32 的 MMIO 集成方式（数字侧）
