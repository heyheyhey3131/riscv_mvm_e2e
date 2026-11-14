// =============================================================================
// 极简地址译码互联
//
// [给你看的对照] 刚学 Python 的话：
//   这是一个「按地址把请求转发出去」的路由器，≈ ISS 里的 mmio_read / mmio_write。
//   if addr[31:16]==16'h2000 → MVM，就像 Python 的 if MVM_BASE <= addr < ...
//
// 结构：一个主端口（CPU）+ 四个从端口（RAM / UART / MVM / TOHOST）。
// 协议：PicoRV32 native memory interface
//   主设备拉高 m_valid 直到从设备给 m_ready；
//   m_wstrb==0 表示读，非 0 表示按字节写。
//
// 译码只看 addr[31:16]，低位原样转发给从设备自己解析偏移。
// 未映射地址：立即 ready、读回 0，避免 CPU 永远等 ready。
//
// clk/rst_n 目前未用（纯组合互联），留着是为以后加寄存器切片。
// =============================================================================

`timescale 1ns / 1ps

module simple_interconnect (
    input  wire        clk,
    input  wire        rst_n,

    // ---- CPU 主端口 ----
    input  wire        m_valid,
    input  wire        m_instr,     // 1=取指，本互联不区分，RAM 统一处理
    output wire        m_ready,
    input  wire [31:0] m_addr,
    input  wire [31:0] m_wdata,
    input  wire [ 3:0] m_wstrb,
    output wire [31:0] m_rdata,

    // ---- 四个从端口，信号一一对应 ----
    output wire        ram_valid,
    input  wire        ram_ready,
    output wire [31:0] ram_addr,
    output wire [31:0] ram_wdata,
    output wire [ 3:0] ram_wstrb,
    input  wire [31:0] ram_rdata,

    output wire        uart_valid,
    input  wire        uart_ready,
    output wire [31:0] uart_addr,
    output wire [31:0] uart_wdata,
    output wire [ 3:0] uart_wstrb,
    input  wire [31:0] uart_rdata,

    output wire        mvm_valid,
    input  wire        mvm_ready,
    output wire [31:0] mvm_addr,
    output wire [31:0] mvm_wdata,
    output wire [ 3:0] mvm_wstrb,
    input  wire [31:0] mvm_rdata,

    output wire        th_valid,
    input  wire        th_ready,
    output wire [31:0] th_addr,
    output wire [31:0] th_wdata,
    output wire [ 3:0] th_wstrb,
    input  wire [31:0] th_rdata
);

// 片选：valid 为 0 时所有 sel 都为 0，从设备不会误响应
wire sel_ram  = m_valid && (m_addr[31:16] == 16'h0000);
wire sel_uart = m_valid && (m_addr[31:16] == 16'h1000);
wire sel_mvm  = m_valid && (m_addr[31:16] == 16'h2000);
wire sel_th   = m_valid && (m_addr[31:16] == 16'h3000);
wire sel_none = m_valid && !(sel_ram || sel_uart || sel_mvm || sel_th);

assign ram_valid  = sel_ram;
assign uart_valid = sel_uart;
assign mvm_valid  = sel_mvm;
assign th_valid   = sel_th;

// 地址/写数据广播，由 valid 决定谁真正收
assign ram_addr  = m_addr;
assign uart_addr = m_addr;
assign mvm_addr  = m_addr;
assign th_addr   = m_addr;

assign ram_wdata  = m_wdata;
assign uart_wdata = m_wdata;
assign mvm_wdata  = m_wdata;
assign th_wdata   = m_wdata;

assign ram_wstrb  = m_wstrb;
assign uart_wstrb = m_wstrb;
assign mvm_wstrb  = m_wstrb;
assign th_wstrb   = m_wstrb;

// ready 多路：无事务时为 0，CPU 的 FETCH/MEM 会继续等
assign m_ready = sel_ram  ? ram_ready  :
                 sel_uart ? uart_ready :
                 sel_mvm  ? mvm_ready  :
                 sel_th   ? th_ready   :
                 sel_none ? 1'b1       : 1'b0;

assign m_rdata = sel_ram  ? ram_rdata  :
                 sel_uart ? uart_rdata :
                 sel_mvm  ? mvm_rdata  :
                 sel_th   ? th_rdata   : 32'b0;

endmodule
