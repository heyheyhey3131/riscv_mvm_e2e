# 内存映射

所有外设 32-bit 字对齐。CPU 是小端。

```
0x0000_0000  RAM  8 KB     代码 + 数据 + 栈（栈顶 0x2000）
0x0000_0010  mtvec         机器外部中断入口（仍在 RAM 里）
0x0000_1F00  irq_flag      固件约定的一字节/一字旗标

0x1000_0000  UART DATA     写低 8 位 = 发送
0x1000_0004  UART STATUS   bit0 = tx_busy

0x2000_0000  MVM CTRL      [0] START(W1P)  [1] IRQ_EN
0x2000_0004  MVM STATUS    [0] BUSY [1] DONE [2] IRQ  [17:16] FSM
0x2000_0008  MVM IRQ       写 1 清中断
0x2000_000C  MVM CONFIG    [7:0] settle  [15:8] adc_cycles
0x2000_0010  MVM INP       {x3,x2,x1,x0} 每字节低 6 bit
0x2000_0020  MVM WROW0     {w0,3 .. w0,0}  行 i 到 4 个输出
0x2000_0024  MVM WROW1
0x2000_0028  MVM WROW2
0x2000_002C  MVM WROW3
0x2000_0050  MVM OUTPACK   {y3,y2,y1,y0}
0x2000_0054  MVM LATENCY   上次运算周期数

0x3000_0000  TOHOST        1=PASS, 3=FAIL
```

## 打包格式

字节 0 是列/输入 0（小端）：

```
word = b0 | (b1<<8) | (b2<<16) | (b3<<24)
```

矩阵约定：`y_j = Σ_i x_i * W[i][j]`，`WROW_i` 的第 j 个字节是 `W[i][j]`。

## CSR（CPU 内部，不是 MMIO）

| CSR | 地址 | 用到的位 |
|---|---|---|
| mstatus | 0x300 | bit3 MIE，bit7 MPIE |
| mie | 0x304 | bit11 MEIE |
| mtvec | 0x305 | 只读 0x10 |
| mepc | 0x341 | 中断返回地址 |
| mcause | 0x342 | 外部中断写 11 |
| mip | 0x344 | bit11 = irq 电平 |

没有实现完整特权态，够用这套即可。
