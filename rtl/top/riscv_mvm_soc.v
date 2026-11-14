// =============================================================================
// 题目 G 教学 SoC
//
// [给你看的对照] 刚学 Python 的话：
//   这是「把零件拼起来」的文件，自己几乎没有算法。
//   module riscv_mvm_soc    ≈  一个大 class，里面 new 了 CPU / 总线 / RAM / MVM
//   u_cpu / u_bus / u_mvm   例化名，≈  self.cpu = ISS(); self.mvm = MvmModel()
//
//   rv32i_min  --mem_*-->  simple_interconnect  --> RAM / UART / MVM / TOHOST
//                                    irq_mvm <---- mvm_copro
//
// INIT_FILE 是 $readmemh 路径，相对仿真工作目录（仓库根）。
// 综合整 SoC 前先确认 SRAM 要换成宏；面积报告请用 mvm_copro_top。
// =============================================================================

`timescale 1ns / 1ps

module riscv_mvm_soc #(
    parameter INIT_FILE = "fw/hex/e2e_mvm.hex"
) (
    input  wire        clk,
    input  wire        rst_n,
    output wire        ser_tx,     // UART 串口，板级才需要
    output wire        irq_mvm,    // 接到 CPU，同时给 TB 计数上升沿
    output wire [31:0] tohost      // TB 轮询，1=PASS
);

wire        mem_valid, mem_instr, mem_ready;
wire [31:0] mem_addr, mem_wdata, mem_rdata;
wire [ 3:0] mem_wstrb;

wire        ram_valid, ram_ready;
wire [31:0] ram_addr, ram_wdata, ram_rdata;
wire [ 3:0] ram_wstrb;

wire        uart_valid, uart_ready;
wire [31:0] uart_addr, uart_wdata, uart_rdata;
wire [ 3:0] uart_wstrb;

wire        mvm_valid, mvm_ready;
wire [31:0] mvm_addr, mvm_wdata, mvm_rdata;
wire [ 3:0] mvm_wstrb;

wire        th_valid, th_ready;
wire [31:0] th_addr, th_wdata, th_rdata;
wire [ 3:0] th_wstrb;

rv32i_min u_cpu (
    .clk       (clk),
    .rst_n     (rst_n),
    .mem_valid (mem_valid),
    .mem_instr (mem_instr),
    .mem_ready (mem_ready),
    .mem_addr  (mem_addr),
    .mem_wdata (mem_wdata),
    .mem_wstrb (mem_wstrb),
    .mem_rdata (mem_rdata),
    .irq       (irq_mvm)
);

simple_interconnect u_bus (
    .clk       (clk),
    .rst_n     (rst_n),
    .m_valid   (mem_valid),
    .m_instr   (mem_instr),
    .m_ready   (mem_ready),
    .m_addr    (mem_addr),
    .m_wdata   (mem_wdata),
    .m_wstrb   (mem_wstrb),
    .m_rdata   (mem_rdata),
    .ram_valid (ram_valid),
    .ram_ready (ram_ready),
    .ram_addr  (ram_addr),
    .ram_wdata (ram_wdata),
    .ram_wstrb (ram_wstrb),
    .ram_rdata (ram_rdata),
    .uart_valid(uart_valid),
    .uart_ready(uart_ready),
    .uart_addr (uart_addr),
    .uart_wdata(uart_wdata),
    .uart_wstrb(uart_wstrb),
    .uart_rdata(uart_rdata),
    .mvm_valid (mvm_valid),
    .mvm_ready (mvm_ready),
    .mvm_addr  (mvm_addr),
    .mvm_wdata (mvm_wdata),
    .mvm_wstrb (mvm_wstrb),
    .mvm_rdata (mvm_rdata),
    .th_valid  (th_valid),
    .th_ready  (th_ready),
    .th_addr   (th_addr),
    .th_wdata  (th_wdata),
    .th_wstrb  (th_wstrb),
    .th_rdata  (th_rdata)
);

sram_1rw #(
    .WORDS     (2048),
    .AW        (11),
    .INIT_FILE (INIT_FILE)
) u_ram (
    .clk   (clk),
    .rst_n (rst_n),
    .valid (ram_valid),
    .ready (ram_ready),
    .addr  (ram_addr),
    .wdata (ram_wdata),
    .wstrb (ram_wstrb),
    .rdata (ram_rdata)
);

uart_tx u_uart (
    .clk   (clk),
    .rst_n (rst_n),
    .valid (uart_valid),
    .ready (uart_ready),
    .addr  (uart_addr),
    .wdata (uart_wdata),
    .wstrb (uart_wstrb),
    .rdata (uart_rdata),
    .ser_tx(ser_tx)
);

mvm_copro u_mvm (
    .clk   (clk),
    .rst_n (rst_n),
    .valid (mvm_valid),
    .ready (mvm_ready),
    .addr  (mvm_addr),
    .wdata (mvm_wdata),
    .wstrb (mvm_wstrb),
    .rdata (mvm_rdata),
    .irq   (irq_mvm)
);

tohost u_th (
    .clk   (clk),
    .rst_n (rst_n),
    .valid (th_valid),
    .ready (th_ready),
    .addr  (th_addr),
    .wdata (th_wdata),
    .wstrb (th_wstrb),
    .rdata (th_rdata),
    .value (tohost)
);

endmodule
