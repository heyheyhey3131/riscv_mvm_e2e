# 协处理器面积与访问延迟（填写）

工艺：TSMC 28HPC+ / 0.9 V  
库 corner：  
时钟约束：20 ns period，uncertainty 4 ns（20% 裕量）  
DUT：`mvm_copro_top`

## 面积

| 项 | 数值 | 来源 |
|---|---|---|
| Combinational |  | DC area.rpt |
| Sequential |  | |
| Buf/Inv |  | |
| Total cell area |  | |
| 版图面积 (μm²) |  | Innovus |

折合 mm²：  

## 访问延迟

| 项 | 周期 | 时间 @50 MHz |
|---|---|---|
| 写 INP+4×WROW |  | |
| settle | 8 | 160 ns |
| adc | 4 | 80 ns |
| 采样打拍 | 1 | 20 ns |
| `MVM_LATENCY` 寄存器 | 13 | 260 ns |
| 中断到读出 OUTPACK |  | SoC 仿真 |

## 时序

| corner | WNS | TNS | 是否满足 20% 裕量 |
|---|---|---|---|
| tt 0.9 V 25C |  |  | |
| ss（若有） |  |  | |
| ff（若有） |  |  | |

## MVM 精度

| 向量 | 最大 \|y-y_gold\| (LSB) |
|---|---|
| zeros |  |
| fullscale |  |
| mixed |  |

结论：误差 ≤ 1 LSB：是 / 否
