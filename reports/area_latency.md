# 协处理器面积与访问延迟

工艺目标：TSMC 28HPC+ / 0.9 V  
DUT：`mvm_copro_top`  
时钟约束：20 ns period，uncertainty 4 ns（20% 裕量写法）  
更新日期：2026-11-02

## 面积

| 项 | 数值 | 来源 |
|---|---|---|
| Combinational | **未测** | 需 DC `area.rpt` |
| Sequential | **未测** | |
| Total cell area | **未测** | |
| 版图面积 (μm²) | **未测** | 需 Innovus |

阻塞：EDA2035 SSH 超时（`192.168.72.143:22`），DC/Innovus 尚未跑。

RTL 规模（便于估工作量，**不能**当签核面积）：

| 文件 | 角色 |
|---|---|
| `rtl/mvm/mvm_array_digital.v` | 4×4 组合 MAC + `/252` |
| `rtl/mvm/mvm_copro.v` | 寄存器堆 + 4 态 FSM |
| `rtl/top/mvm_copro_top.v` | ASIC 顶层包装 |

## 访问延迟（已测）

周期精确 FSM（`scripts/sim/check_copro_fsm.py`，对齐 RTL）：

| 项 | 周期 | @50 MHz |
|---|---|---|
| settle | 8 | 160 ns |
| adc | 4 | 80 ns |
| 采样打拍 | 1 | 20 ns |
| **MVM_LATENCY** | **13** | **260 ns** |
| START→DONE/IRQ | 13 | 260 ns |
| IRQ 后 W1C | 立即落下 | — |

ISS 端到端（`reports/iss_e2e.json`）三次运算的 `start → irq_enter` 间隔均为 13 条指令，与 `MVM_LATENCY=13` 一致。

软件开销（含写寄存器、进中断、黄金比对）三次向量合计 **5658** 条指令。这不是协处理器硬件延迟，写报告时不要混。

## 时序 / PVT

| corner | WNS | 20% 裕量 |
|---|---|---|
| tt 0.9 V 25C | **未测** | SDC 已写 uncertainty=4 ns，PT 未跑 |
| ss / ff | **未测** | 库是否有该 corner 待 VM 确认 |

## 精度（已测，见 `precision.json`）

| 条件 | 最大误差 | ≤1 LSB？ |
|---|---|---|
| 整数黄金自洽 500 组 | 0 LSB | 是 |
| 无失配实数模型 500 组 | 1 LSB | 是 |
| ±1% 电导失配 500 组 | 1 LSB | 是 |
| ±5% 电导失配 500 组 | 2 LSB（14/500 超标） | 否（敏感度，非题目理想阵列要求） |
