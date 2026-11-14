// =============================================================================
// SoC 冒烟：跑 fw/hex/smoke.S
//
// [给你看的对照] 刚学 Python 的话：
//   把整颗 SoC 例化出来，加载 smoke.hex，等 tohost==1。
//   相当于 python scripts/sim/iss.py fw/hex/smoke.hex，只不过这里是 Verilog 仿真。
// 只证明 CPU 能取指、lui/addi/sw、写 TOHOST=1。不过 MVM、不开中断。
// 若本 TB 失败，先别跑 e2e，问题在核或 RAM 加载。
// =============================================================================
`timescale 1ns / 1ps

module tb_soc_smoke;
    reg clk;
    reg rst_n;
    wire ser_tx;
    wire irq_mvm;
    wire [31:0] tohost;

    integer timeout_cyc;

    riscv_mvm_soc #(
        .INIT_FILE("fw/hex/smoke.hex")
    ) dut (
        .clk     (clk),
        .rst_n   (rst_n),
        .ser_tx  (ser_tx),
        .irq_mvm (irq_mvm),
        .tohost  (tohost)
    );

    initial clk = 1'b0;
    always #10 clk = ~clk;

    initial begin
        timeout_cyc = 0;
        rst_n = 0;
        repeat (8) @(posedge clk);
        rst_n = 1;
        while (tohost == 32'd0) begin
            @(posedge clk);
            timeout_cyc = timeout_cyc + 1;
            if (timeout_cyc > 20000) begin
                $display("SMOKE_TIMEOUT pc=%h", dut.u_cpu.pc);
                $fatal;
            end
        end
        $display("tohost=%0d cycles=%0d", tohost, timeout_cyc);
        if (tohost == 32'd1) begin
            $display("SMOKE_PASS");
            $finish;
        end
        $display("SMOKE_FAIL");
        $fatal;
    end
endmodule
