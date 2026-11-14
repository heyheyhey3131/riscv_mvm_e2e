// =============================================================================
// 同步 1RW SRAM 行为模型
//
// [给你看的对照] 刚学 Python 的话：
//   mem[0:WORDS-1]  ≈  ISS 里的 self.mem = bytearray(8192)，一块可读写的数组
//   $readmemh(INIT_FILE, mem)  启动时把 .hex 填进数组，≈ ISS.__init__ 里读 hex 文件
//
// ASIC 流片时把本模块换成 SRAM 编译器宏 + wrapper。
// 教学仿真用二维 reg 数组即可。
//
// 时序（与 PicoSoC 相同，1 拍延迟）：
//   周期 0：CPU 拉 valid，本拍 ready=0
//   上升沿：采样地址，rdata<=mem[addr]，若 wstrb 则写入，ready<=1
//   周期 1：CPU 看到 ready=1 和有效 rdata，撤销 valid
//
// 读优先：同一拍既读又写时，rdata 拿到的是写之前的旧值。
// 取指 wstrb=0，不受影响。
// =============================================================================

`timescale 1ns / 1ps

module sram_1rw #(
    parameter integer WORDS = 2048,   // 默认 8 KB
    parameter integer AW    = 11,     // $clog2(WORDS)，写死以免老 iverilog 不认
    parameter INIT_FILE     = ""      // $readmemh 路径，相对仿真工作目录
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid,
    output reg         ready,
    input  wire [31:0] addr,
    input  wire [31:0] wdata,
    input  wire [ 3:0] wstrb,         // 每个 bit 对应一个字节
    output reg  [31:0] rdata
);

reg [31:0] mem [0:WORDS-1];

// 字地址：丢掉字节偏移 addr[1:0]
wire [AW-1:0] waddr = addr[AW+1:2];

initial begin
    if (INIT_FILE != "") begin
        $readmemh(INIT_FILE, mem);
    end
end

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        ready <= 1'b0;
        rdata <= 32'b0;
        // 不把 mem 清零：hex 已在 initial 里装好，复位不应擦程序
    end else begin
        ready <= 1'b0;
        // !ready 防止 valid 多停一拍时把同一地址写两遍
        if (valid && !ready) begin
            rdata <= mem[waddr];
            if (wstrb[0]) mem[waddr][ 7: 0] <= wdata[ 7: 0];
            if (wstrb[1]) mem[waddr][15: 8] <= wdata[15: 8];
            if (wstrb[2]) mem[waddr][23:16] <= wdata[23:16];
            if (wstrb[3]) mem[waddr][31:24] <= wdata[31:24];
            ready <= 1'b1;
        end
    end
end

endmodule
