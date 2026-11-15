// 实数域 4x4 电流型阵列 + 6-bit ADC。用于混合信号行为仿真，不综合。
//
// [给你看的对照] 刚学 Python 的话：
//   本模块 ≈ golden/mvm_ref.py 的 mvm_real()：用伏特/西门子算电流，再量化成 6-bit。
//   parameter real VREF = 0.6  ≈  函数默认参数 vref=0.6，综合工具会忽略 real。
// 物理量：t28 0.9 V 教学设定
//   Vin = (x/63)*0.6 V
//   G   = w * 1 uS
//   Ij  = sum Vin_i * G_ij
//   Ifs = 4 * 0.6 V * 63 uS
//   code = round(Ij/Ifs * 63)

`timescale 1ns / 1ps

// 失配（mismatch）在 golden/mvm_ref.py 的 mvm_real() 里做 Monte Carlo；
// 本模块是理想实数阵列，不保留未使用的 MISMATCH 参数，避免“写了却没生效”。
// 不综合：含 real。有 Spectre 时改用 analog/*.va。
module mvm_array_real #(
    parameter real VREF   = 0.6,      // 输入满码对应 0.6 V，留出到 0.9 V 的余量
    parameter real G_UNIT = 1.0e-6    // 1 LSB 电导 = 1 µS
) (
    input  wire [31:0] xin,
    input  wire [31:0] wrow0,
    input  wire [31:0] wrow1,
    input  wire [31:0] wrow2,
    input  wire [31:0] wrow3,
    output reg  [31:0] ypack,
    output real        iout0,
    output real        iout1,
    output real        iout2,
    output real        iout3
);

function automatic integer clamp6;
    input integer v;
    begin
        if (v < 0) clamp6 = 0;
        else if (v > 63) clamp6 = 63;
        else clamp6 = v;
    end
endfunction

function automatic [5:0] b6;
    input [31:0] w;
    input integer idx;
    begin
        b6 = w[8*idx +: 6];
    end
endfunction

real vin[0:3];
real g[0:3][0:3];
real iout[0:3];
real ifs;
integer yi[0:3];
integer i, j;

always @(*) begin
    vin[0] = (b6(xin, 0) / 63.0) * VREF;
    vin[1] = (b6(xin, 1) / 63.0) * VREF;
    vin[2] = (b6(xin, 2) / 63.0) * VREF;
    vin[3] = (b6(xin, 3) / 63.0) * VREF;

    g[0][0] = b6(wrow0, 0) * G_UNIT;
    g[0][1] = b6(wrow0, 1) * G_UNIT;
    g[0][2] = b6(wrow0, 2) * G_UNIT;
    g[0][3] = b6(wrow0, 3) * G_UNIT;
    g[1][0] = b6(wrow1, 0) * G_UNIT;
    g[1][1] = b6(wrow1, 1) * G_UNIT;
    g[1][2] = b6(wrow1, 2) * G_UNIT;
    g[1][3] = b6(wrow1, 3) * G_UNIT;
    g[2][0] = b6(wrow2, 0) * G_UNIT;
    g[2][1] = b6(wrow2, 1) * G_UNIT;
    g[2][2] = b6(wrow2, 2) * G_UNIT;
    g[2][3] = b6(wrow2, 3) * G_UNIT;
    g[3][0] = b6(wrow3, 0) * G_UNIT;
    g[3][1] = b6(wrow3, 1) * G_UNIT;
    g[3][2] = b6(wrow3, 2) * G_UNIT;
    g[3][3] = b6(wrow3, 3) * G_UNIT;

    ifs = 4.0 * VREF * 63.0 * G_UNIT;
    for (j = 0; j < 4; j = j + 1) begin
        iout[j] = 0.0;
        for (i = 0; i < 4; i = i + 1)
            iout[j] = iout[j] + vin[i] * g[i][j];
        if (ifs <= 0)
            yi[j] = 0;
        else
            yi[j] = clamp6(integer'($rtoi(iout[j] / ifs * 63.0 + 0.5)));
    end
    iout0 = iout[0];
    iout1 = iout[1];
    iout2 = iout[2];
    iout3 = iout[3];
    ypack = {2'b0, yi[3][5:0], 2'b0, yi[2][5:0], 2'b0, yi[1][5:0], 2'b0, yi[0][5:0]};
end

endmodule
