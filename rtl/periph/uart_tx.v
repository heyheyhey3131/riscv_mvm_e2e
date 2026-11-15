// =============================================================================
// 极简 UART 发送器
//
// [给你看的对照] 刚学 Python 的话：
//   写 DATA 寄存器 = 发送一个字符。ISS 里对应 mmio_write(UART_DATA) 然后 print。
//   硬件还要按比特把字符移出去（ser_tx）；ISS 偷懒，直接把字节打印到终端。
//
// 寄存器：
//   offset 0 DATA    写低 8 位启动一次发送；busy 时 ready=0，CPU 会保持事务
//   offset 4 STATUS  读 bit0 = busy；rdata 组合给出，同周期可读
//
// 帧格式：1 start + 8 data LSB first + 1 stop，无校验。
// DIV 是每个 bit 持续的额外周期数（bit 宽 = DIV+1 拍）。
//
// 仿真里 TB 通常直接监听 CPU 写 DATA 的总线事务打印字符，
// 不一定要解码 ser_tx。ser_tx 留给后仿 / FPGA 板级。
// =============================================================================

`timescale 1ns / 1ps

module uart_tx #(
    parameter integer DIV = 4
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid,
    output wire        ready,
    input  wire [31:0] addr,
    input  wire [31:0] wdata,
    input  wire [ 3:0] wstrb,
    output wire [31:0] rdata,
    output reg         ser_tx
);

reg [9:0] sh;          // {stop, data[7:0], start}，最低位先出
reg [3:0] bitcnt;      // 还剩几位，0 表示空闲
reg [15:0] divcnt;
wire busy = (bitcnt != 4'd0);

// 读状态随时可答；写数据在 busy 时必须反压，否则 UART 会静默丢字符。
assign ready = valid && ((wstrb == 4'b0000) || !busy);
assign rdata = {31'b0, busy};

wire wr_data = valid && (addr[3:0] == 4'h0) && wstrb[0];

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        sh     <= 10'h3FF;   // 全 1 = 线路空闲高电平
        bitcnt <= 4'd0;
        divcnt <= 16'd0;
        ser_tx <= 1'b1;
    end else begin
        if (wr_data && !busy) begin
            // start=0, data, stop=1
            sh     <= {1'b1, wdata[7:0], 1'b0};
            bitcnt <= 4'd10;
            divcnt <= 16'd0;
        end else if (busy) begin
            if (divcnt == DIV[15:0]) begin
                divcnt <= 16'd0;
                sh     <= {1'b1, sh[9:1]};  // 右移，高位补 1 保持 stop 后空闲
                bitcnt <= bitcnt - 4'd1;
            end else
                divcnt <= divcnt + 16'd1;
        end
        ser_tx <= sh[0];
    end
end

endmodule
