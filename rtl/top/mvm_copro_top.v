// =============================================================================
// 协处理器 ASIC 顶层
//
// [给你看的对照] 刚学 Python 的话：
//   这是一层薄包装：把 mvm_copro 的端口原样接到芯片引脚。
//   DC / Innovus 综合本模块，不要综合带 8 KB RAM 的整 SoC。
//   相当于 Python 里 def main(): 只调用已有函数，自己不写新逻辑。
//
// 题目 G 要报告「协处理器面积与访问延迟」，所以 DC / Innovus 的 DUT
// 用本模块，不要综合带 8 KB 行为 RAM 的 riscv_mvm_soc。
//
// 端口就是一条 PicoRV32 风格从机总线 + irq。
// 约束见 constraints/mvm_copro_top.sdc（50 MHz + 4 ns uncertainty = 20% 裕量）。
// =============================================================================

`timescale 1ns / 1ps

module mvm_copro_top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid,
    output wire        ready,
    input  wire [31:0] addr,
    input  wire [31:0] wdata,
    input  wire [ 3:0] wstrb,
    output wire [31:0] rdata,
    output wire        irq
);

mvm_copro u_mvm (
    .clk   (clk),
    .rst_n (rst_n),
    .valid (valid),
    .ready (ready),
    .addr  (addr),
    .wdata (wdata),
    .wstrb (wstrb),
    .rdata (rdata),
    .irq   (irq)
);

endmodule
