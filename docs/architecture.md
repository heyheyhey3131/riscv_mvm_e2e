# 架构说明

## 一句话

一颗最小 RISC-V SoC 把 4×4 模拟矩阵向量乘当成 **内存映射协处理器**：CPU 写输入/权重，发 start，等 IRQ，读 6-bit 结果，和黄金值比。

## 为什么总线挂协处理器，而不是 PCPI？

PicoRV32 有 PCPI（自定义指令口），适合 `mul` 这种单指令。MVM 要写 16 个权重 + 4 个输入 + 等待模拟建立时间，用 **MMIO 寄存器** 更接近真实 CIM/NPU 集成方式，也方便换成 AXI-Lite。

本项目 CPU 的 `mem_*` 口与 PicoRV32 native memory interface 相同，以后可以整核替换。

## 数据怎么走

```
固件里的 x[4], W[4][4]
        │  sw 到 0x2000_0010 / 0x2000_0020
        ▼
   mvm_copro 寄存器
        │ START
        ▼
   SETTLE  (模拟 DAC/阵列建立，默认 8 拍)
        ▼
   ADC     (量化，默认 4 拍)
        ▼
   y = quant(Σ x_i w_ij / 252)     6-bit × 4
        │ DONE + IRQ
        ▼
   中断处理程序清 IRQ、置 ram[0x1F00]=1
        ▼
   main 读 OUTPACK，软件再算一遍黄金值，允许 ±1 LSB
        ▼
   UART 打印 PASS，TOHOST=1
```

## 模块职责

| 模块 | 文件 | 综合？ | 作用 |
|---|---|---|---|
| `rv32i_min` | `rtl/core/rv32i_min.v` | 是 | 多周期 RV32I + mstatus/mie/mret |
| `simple_interconnect` | `rtl/bus/simple_interconnect.v` | 是 | 按地址高 16 位译码 |
| `sram_1rw` | `rtl/mem/sram_1rw.v` | 仿真；ASIC 换宏 | 8 KB 统一 RAM |
| `uart_tx` | `rtl/periph/uart_tx.v` | 是 | 打印 PASS/FAIL |
| `tohost` | `rtl/periph/tohost.v` | 仿真邮箱 | 停机码 |
| `mvm_copro` | `rtl/mvm/mvm_copro.v` | 是 | 寄存器+FSM+IRQ |
| `mvm_array_digital` | `rtl/mvm/mvm_array_digital.v` | 是 | 整数点积/量化 |
| `mvm_array_real` | `tb/mixed/mvm_array_real.sv` | 否 | 电压/电导实数模型 |
| Verilog-A | `analog/*.va` | 否 | Spectre AMS |

## 延迟从哪来

协处理器故意 **不** 在 1 拍内算完，否则「模拟 ADC」没有时间含义。

```
latency = settle_cycles + adc_cycles + 1
默认     = 8 + 4 + 1 = 13 cycle
@50 MHz  = 260 ns
```

数字点积本身是组合逻辑，在 ADC 最后一拍采样进 `OUTPACK`。若以后换成真正的 Verilog-A 阵列，只要 settle 大于 DAC 建立时间即可。

## 中断握手

1. 固件置 `mstatus.MIE`、`mie.MEIE`、`MVM_CTRL.IRQ_EN`
2. 写 `START`
3. FSM 到 DONE 时 `irq` 拉高（电平，直到 W1C）
4. CPU 在指令边界进入 `0x10`
5. handler 向 `MVM_IRQ` 写 1，向 `0x1F00` 写 1，`mret`
6. main 看到 flag 再读结果

测试台同时计数 `irq` 上升沿，防止「只 poll STATUS、中断是假的」。
