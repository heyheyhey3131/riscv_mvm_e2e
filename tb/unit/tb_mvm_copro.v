// =============================================================================
// 协处理器单元测试：不经过 CPU
//
// [给你看的对照] 刚学 Python 的话：
//   testbench ≈ 一段测试脚本。这里不跑 CPU，直接拨 valid/addr/wdata，
//   相当于 Python 里 check_copro_fsm.py 的 CoproRtlFsm().write() / .tick()。
//
// 证明：寄存器读写、LATENCY=13、IRQ 上升沿、三组向量误差 ≤ 1 LSB。
// 向量常量必须与 golden/vectors.json、fw/asm/e2e_mvm.S 一致。
// 时钟 10 ns 周期（100 MHz）只为跑得快，和 SoC 50 MHz 约束无关。
// =============================================================================
`timescale 1ns / 1ps

module tb_mvm_copro;
    reg         clk;
    reg         rst_n;
    reg         valid;
    wire        ready;
    reg  [31:0] addr;
    reg  [31:0] wdata;
    reg  [ 3:0] wstrb;
    wire [31:0] rdata;
    wire        irq;

    integer errors;
    integer irq_seen;

    mvm_copro_top dut (
        .clk   (clk),
        .rst_n (rst_n),
        .valid (valid),
        .ready (ready),
        .addr  (addr),
        .wdata (wdata),
        .wstrb (wstrb),
        .rdata (rdata),
        .irq   (irq)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    always @(posedge irq) irq_seen = irq_seen + 1;

    // PicoRV32 风格：拉 valid 等到 ready。DUT ready 与 valid 同周期。
    task mmio_write;
        input [31:0] a;
        input [31:0] d;
        begin
            @(posedge clk);
            valid <= 1'b1;
            addr  <= a;
            wdata <= d;
            wstrb <= 4'hF;
            @(posedge clk);
            while (!ready) @(posedge clk);
            valid <= 1'b0;
            wstrb <= 4'h0;
        end
    endtask

    task mmio_read;
        input  [31:0] a;
        output [31:0] d;
        begin
            @(posedge clk);
            valid <= 1'b1;
            addr  <= a;
            wdata <= 32'b0;
            wstrb <= 4'h0;
            @(posedge clk);
            while (!ready) @(posedge clk);
            d = rdata;
            valid <= 1'b0;
        end
    endtask

    // 写向量 → START|IRQ_EN → 等 STATUS.DONE → 按字节比 |got-exp|<=1
    task run_vec;
        input [31:0] xin;
        input [31:0] w0, w1, w2, w3;
        input [31:0] yexp;
        integer i;
        reg [31:0] ygot, lat, st;
        reg [7:0] ge, go, diff;
        begin
            mmio_write(32'h2000_0008, 32'd1); // clear irq
            mmio_write(32'h2000_0010, xin);
            mmio_write(32'h2000_0020, w0);
            mmio_write(32'h2000_0024, w1);
            mmio_write(32'h2000_0028, w2);
            mmio_write(32'h2000_002C, w3);
            mmio_write(32'h2000_0000, 32'd3); // START|IRQ_EN
            i = 0;
            st = 0;
            while (!st[1] && i < 1000) begin
                mmio_read(32'h2000_0004, st);
                i = i + 1;
            end
            mmio_read(32'h2000_0050, ygot);
            mmio_read(32'h2000_0054, lat);
            $display("  xin=%h ygot=%h yexp=%h latency=%0d irq=%0d", xin, ygot, yexp, lat, irq);
            if (lat != 13) begin
                $display("ERROR latency %0d != 13", lat);
                errors = errors + 1;
            end
            for (i = 0; i < 4; i = i + 1) begin
                go = ygot[8*i +: 8];
                ge = yexp[8*i +: 8];
                diff = (go > ge) ? (go - ge) : (ge - go);
                if (diff > 8'd1) begin
                    $display("ERROR col %0d got=%0d exp=%0d", i, go, ge);
                    errors = errors + 1;
                end
            end
        end
    endtask

    initial begin
        errors   = 0;
        irq_seen = 0;
        clk      = 0;
        rst_n    = 0;
        valid    = 0;
        addr     = 0;
        wdata    = 0;
        wstrb    = 0;
        repeat (5) @(posedge clk);
        rst_n = 1;
        mmio_write(32'h2000_000C, 32'h00000408);

        $display("vector zeros");
        run_vec(32'h00000000, 32'h0, 32'h0, 32'h0, 32'h0, 32'h00000000);

        $display("vector fullscale");
        run_vec(32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f, 32'h3f3f3f3f);

        $display("vector mixed");
        run_vec(32'h3f3c3228, 32'h1e140a28, 32'h1e141428, 32'h1e141e28, 32'h1e142828, 32'h19101621);

        if (irq_seen < 3) begin
            $display("ERROR irq_seen=%0d", irq_seen);
            errors = errors + 1;
        end

        if (errors == 0) begin
            $display("TB_MVM_PASS");
            $finish;
        end else begin
            $display("TB_MVM_FAIL errors=%0d", errors);
            $fatal;
        end
    end

    initial begin
        #200000;
        $display("TIMEOUT");
        $fatal;
    end
endmodule
