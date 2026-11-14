// =============================================================================
// 混合行为仿真（不需要 Spectre / AMS）
//
// [给你看的对照] 刚学 Python 的话：
//   同一组 x/W 同时喂给整数阵列和 real 阵列，比误差。
//   相当于 check_precision.py 里 mvm_int() vs mvm_real()，只是用 SystemVerilog 写。
// 同一组向量同时喂给 mvm_array_digital（整数）和 mvm_array_real（伏特/西门子）。
// 理想参数下两者应逐码相等；断言允许 1 LSB，对应题目精度。
// 用 VCS/Xcelium：scripts/sim/run_vcs.sh 最后一段。
// =============================================================================

`timescale 1ns / 1ps

module tb_mixed_sv;
    integer errors;
    reg [31:0] xin, w0, w1, w2, w3;
    wire [31:0] y_real, y_dig;

    mvm_array_digital u_dig (
        .xin(xin), .wrow0(w0), .wrow1(w1), .wrow2(w2), .wrow3(w3), .ypack(y_dig)
    );

    mvm_array_real u_real (
        .xin(xin), .wrow0(w0), .wrow1(w1), .wrow2(w2), .wrow3(w3),
        .ypack(y_real),
        .iout0(), .iout1(), .iout2(), .iout3()
    );

    task check;
        input [31:0] x, a, b, c, d;
        integer k, ge, gr, diff;
        begin
            xin = x; w0 = a; w1 = b; w2 = c; w3 = d;
            #1;
            $display("x=%h dig=%h real=%h I-scale check", x, y_dig, y_real);
            for (k = 0; k < 4; k = k + 1) begin
                ge = y_dig[8*k +: 8];
                gr = y_real[8*k +: 8];
                diff = (ge > gr) ? (ge - gr) : (gr - ge);
                if (diff > 1) begin
                    $display("ERROR col %0d dig=%0d real=%0d", k, ge, gr);
                    errors = errors + 1;
                end
            end
        end
    endtask

    initial begin
        errors = 0;
        check(32'h00000000, 0, 0, 0, 0);
        check(32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f);
        check(32'h3f3c3228, 32'h1e140a28, 32'h1e141428, 32'h1e141e28, 32'h1e142828);
        if (errors == 0) begin
            $display("MIXED_SV_PASS");
            $finish;
        end
        $display("MIXED_SV_FAIL");
        $fatal;
    end
endmodule
