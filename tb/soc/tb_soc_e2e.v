// =============================================================================
// SoC 端到端：跑 fw/hex/e2e_mvm.hex
//
// [给你看的对照] 刚学 Python 的话：
//   相当于 python scripts/sim/iss.py fw/hex/e2e_mvm.hex --report ...
//   通过条件同样是 tohost==1，并且 irq 上升沿至少 3 次。
//
// 通过条件：tohost==1 且 irq 上升沿 ≥ 3（三组向量各一次中断）。
// UART 打印靠监听 CPU 写 0x1000_0000，不解码 ser_tx。
// hex 路径相对仿真工作目录，请在仓库根运行 iverilog/vcs。
// =============================================================================
`timescale 1ns / 1ps

module tb_soc_e2e;
    reg clk;
    reg rst_n;
    wire ser_tx;
    wire irq_mvm;
    wire [31:0] tohost;

    integer irq_count;
    integer timeout_cyc;

    riscv_mvm_soc #(
        .INIT_FILE("fw/hex/e2e_mvm.hex")
    ) dut (
        .clk     (clk),
        .rst_n   (rst_n),
        .ser_tx  (ser_tx),
        .irq_mvm (irq_mvm),
        .tohost  (tohost)
    );

    initial clk = 1'b0;
    always #10 clk = ~clk; // 50 MHz, 对应 t28 教学约束

    always @(posedge irq_mvm) irq_count = irq_count + 1;

    always @(posedge clk) begin
        if (rst_n && dut.mem_valid && dut.mem_ready && |dut.mem_wstrb &&
            dut.mem_addr == 32'h1000_0000) begin
            $write("%c", dut.mem_wdata[7:0]);
        end
    end

    initial begin
        irq_count   = 0;
        timeout_cyc = 0;
        clk   = 0;
        rst_n = 0;
        repeat (8) @(posedge clk);
        rst_n = 1;

        while (tohost == 32'd0) begin
            @(posedge clk);
            timeout_cyc = timeout_cyc + 1;
            if (timeout_cyc > 400000) begin
                $display("\nTIMEOUT pc=%h tohost=%h irq=%0d", dut.u_cpu.pc, tohost, irq_count);
                $fatal;
            end
        end

        $display("");
        $display("tohost=%0d cycles=%0d irq_count=%0d", tohost, timeout_cyc, irq_count);
        if (tohost == 32'd1 && irq_count >= 3) begin
            $display("SOC_E2E_PASS");
            $finish;
        end else begin
            $display("SOC_E2E_FAIL");
            $fatal;
        end
    end
endmodule
