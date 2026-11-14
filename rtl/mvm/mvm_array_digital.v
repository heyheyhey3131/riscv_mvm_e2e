// =============================================================================
// 4x4 理想电流型 MVM 的数字等价模型（可综合）
//
// [给你看的对照] 刚学 Python 的话：
//   本模块 ≈ golden/mvm_ref.py 里的 mvm_int()，公式完全相同：y = sum(x*w) // 252
//   assign y0 = quant6(...)   ≈  y0 = clamp6(acc // 252)，但是硬件里一直在算
//   function quant6           ≈  def clamp6(v)，给组合逻辑用的小函数
//
// 模拟图像：I_j = Σ_i V_i * G_ij
// 数字编码：x_i, w_ij ∈ [0, 63]
//           acc_j     = Σ_i x_i * w_ij          ∈ [0, 15876]
//           y_j       = clip(acc_j / 252, 0, 63)
//
// 252 = 4*63*63 / 63，所以四个输入、四个权重全满码时 y=63。
// 本模块是组合逻辑，采样打拍在 mvm_copro 的 ADC 最后一拍完成。
//
// 打包格式（小端，每字节低 6 bit 有效，高 2 bit 为 0）：
//   xin   = {x3, x2, x1, x0}
//   wrow_i 的 byte_j = W[i][j]     （行 i → 四个输出列）
//   ypack = {y3, y2, y1, y0}
// =============================================================================

`timescale 1ns / 1ps

module mvm_array_digital (
    input  wire [31:0] xin,
    input  wire [31:0] wrow0,
    input  wire [31:0] wrow1,
    input  wire [31:0] wrow2,
    input  wire [31:0] wrow3,
    output wire [31:0] ypack
);

wire [5:0] x [0:3];
wire [5:0] w [0:3][0:3];

// 只取每字节低 6 bit，和固件 & 0x3f 的效果相同
assign x[0] = xin[5:0];
assign x[1] = xin[13:8];
assign x[2] = xin[21:16];
assign x[3] = xin[29:24];

assign w[0][0] = wrow0[5:0];
assign w[0][1] = wrow0[13:8];
assign w[0][2] = wrow0[21:16];
assign w[0][3] = wrow0[29:24];
assign w[1][0] = wrow1[5:0];
assign w[1][1] = wrow1[13:8];
assign w[1][2] = wrow1[21:16];
assign w[1][3] = wrow1[29:24];
assign w[2][0] = wrow2[5:0];
assign w[2][1] = wrow2[13:8];
assign w[2][2] = wrow2[21:16];
assign w[2][3] = wrow2[29:24];
assign w[3][0] = wrow3[5:0];
assign w[3][1] = wrow3[13:8];
assign w[3][2] = wrow3[21:16];
assign w[3][3] = wrow3[29:24];

// Verilog 整数除法向 0 取整，与 Python // 对非负数一致
function [5:0] quant6;
    input integer acc;
    integer q;
    begin
        if (acc < 0)
            q = 0;
        else
            q = acc / 252;
        if (q > 63)
            q = 63;
        quant6 = q[5:0];
    end
endfunction

wire [5:0] y0, y1, y2, y3;

// y_j = quant(Σ_i x_i * W[i][j])
assign y0 = quant6(x[0]*w[0][0] + x[1]*w[1][0] + x[2]*w[2][0] + x[3]*w[3][0]);
assign y1 = quant6(x[0]*w[0][1] + x[1]*w[1][1] + x[2]*w[2][1] + x[3]*w[3][1]);
assign y2 = quant6(x[0]*w[0][2] + x[1]*w[1][2] + x[2]*w[2][2] + x[3]*w[3][2]);
assign y3 = quant6(x[0]*w[0][3] + x[1]*w[1][3] + x[2]*w[2][3] + x[3]*w[3][3]);

// 每字节 {2'b0, y}，extract_byte 取 8 bit 时高位为 0
assign ypack = {2'b0, y3, 2'b0, y2, 2'b0, y1, 2'b0, y0};

endmodule
