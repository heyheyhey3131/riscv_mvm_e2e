`ifndef SOC_CFG_VH
`define SOC_CFG_VH

// =============================================================================
// SoC 地址与量化常量
//
// [给你看的对照] 刚学 Python 的话：
//   本文件 ≈ fw/python/socmap.py 的 Verilog 翻译。
//   `define MVM_BASE 32'h2000_0000   ≈  Python 的 MVM_BASE = 0x20000000
//   `ifndef / `define / `endif       和 C 的头文件卫士一样，防止重复包含
//
// 三份必须保持字节级一致，改一处就要改另外两处：
//   rtl/include/soc_cfg.vh     本文件（Verilog 宏，给 RTL / TB）
//   fw/include/mvm_hw.h        C 固件
//   fw/python/socmap.py        汇编器、ISS、黄金模型
//
// 译码规则：互联核看 addr[31:16]
//   0x0000  RAM     8 KB 统一指令/数据空间
//   0x1000  UART
//   0x2000  MVM 协处理器
//   0x3000  TOHOST 仿真停机邮箱
// =============================================================================

// ---- RAM：代码、数据、栈都在这里。栈从高地址往下长 ----
`define RAM_BASE        32'h0000_0000
`define RAM_BYTES       32'd8192          // 8 KB
`define RAM_WORDS       2048              // 按 32-bit 字计
`define RAM_ADDR_HI     12                // 字地址用 addr[12:2]

`define UART_BASE       32'h1000_0000
`define UART_DATA       32'h1000_0000     // 写低 8 位 = 发送一字节
`define UART_STATUS     32'h1000_0004     // bit0 = tx_busy

`define MVM_BASE        32'h2000_0000
`define MVM_CTRL        32'h2000_0000     // [0] START 写脉冲, [1] IRQ_EN
`define MVM_STATUS      32'h2000_0004     // [0] BUSY [1] DONE [2] IRQ
`define MVM_IRQ         32'h2000_0008     // 写 1 清中断（W1C）
`define MVM_CONFIG      32'h2000_000C     // [7:0] settle, [15:8] adc 拍数
`define MVM_INP         32'h2000_0010     // {x3,x2,x1,x0} 每字节低 6 bit
`define MVM_WROW0       32'h2000_0020     // 第 0 行权重 → 四个输出列
`define MVM_WROW1       32'h2000_0024
`define MVM_WROW2       32'h2000_0028
`define MVM_WROW3       32'h2000_002C
`define MVM_OUTPACK     32'h2000_0050     // {y3,y2,y1,y0} 只读
`define MVM_LATENCY     32'h2000_0054     // 上次运算周期数，写报告用

`define TOHOST_BASE     32'h3000_0000     // 1=PASS, 3=FAIL

`define RESET_PC        32'h0000_0000     // 复位后从 RAM 0 取指
`define MTVEC_RESET     32'h0000_0010     // 机器外部中断入口（仍在 RAM）
`define STACK_TOP       32'h0000_2000     // 8 KB 末尾，sp 初值

// ---- 6-bit 电流型 MVM 的数字量化 ----
// acc_j = Σ_i x_i * w_ij            x,w ∈ [0,63]
// y_j   = acc_j / 252               向 0 取整，再 clip 到 0..63
// 因为 4*63*63 = 15876，15876/63 = 252，满码进恰好满码出。
`define MVM_N           4
`define MVM_BITS        6
`define MVM_MAX         63
`define MVM_SCALE       252

// 协处理器 FSM 默认等待拍数：模拟 DAC 建立 + ADC 量化
`define MVM_SETTLE_DFLT 8
`define MVM_ADC_DFLT    4

`endif
