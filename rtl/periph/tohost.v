// =============================================================================
// 仿真停机邮箱（Spike / RISC-V 测试常用约定）
//
// [给你看的对照] 刚学 Python 的话：
//   一个 32-bit 寄存器。固件写 1=PASS、3=FAIL。
//   ISS 里对应 self.tohost；run() 循环 while self.tohost == 0。
//
// 固件向 0x3000_0000 写：
//   1 = PASS
//   3 = FAIL（或其他非 1 值）
//
// TB / ISS 轮询 value，非 0 就结束仿真。
// 综合进芯片也可以留着当 debug 寄存器；没有测试台时只是普通 MMIO。
// rdata 组合读出，避免 CPU 采到旧值。
// =============================================================================

`timescale 1ns / 1ps

module tohost (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid,
    output wire        ready,
    input  wire [31:0] addr,     // 片选已由互联完成，偏移不用再译
    input  wire [31:0] wdata,
    input  wire [ 3:0] wstrb,
    output wire [31:0] rdata,
    output wire [31:0] value     // 给 TB 用的观察口
);

assign ready = valid;
reg [31:0] th;

assign value = th;
assign rdata = th;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        th <= 32'b0;
    end else begin
        if (valid && |wstrb)
            th <= wdata;
    end
end

endmodule
