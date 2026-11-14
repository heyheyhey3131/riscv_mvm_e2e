// =============================================================================
// MVM 协处理器：寄存器从机 + 时序 FSM + 4x4 数字阵列
//
// [给你看的对照] 刚学 Python 的话：
//   module mvm_copro (...)  ≈  class MvmModel（见 scripts/sim/iss.py）
//   input/output            ≈  函数参数 / 返回值，但是是一直存在的端口
//   always @(posedge clk)   ≈  每个时钟沿自动跑一遍的函数（ISS 里叫 tick()）
//   reg                     ≈  self.ctrl / self.state 这种会记住上次值的变量
//
// 访问延迟（可在 LATENCY 寄存器读回，用来填题目报告）：
//   latency = settle_cycles + adc_cycles + 1
//   默认     = 8 + 4 + 1 = 13 拍
//   @50 MHz  = 260 ns
//
// 数字点积本身是组合的；FSM 的 SETTLE/ADC 计数是给「模拟建立时间」占位置。
// 换成 Verilog-A 阵列时，只要 settle 大于 DAC 建立即可，寄存器地图不用改。
//
// 中断：DONE 且 IRQ_EN=1 时 irq 变高（电平），软件向 IRQ 写 1 才放下。
// ready 与 valid 同周期，rdata 必须是组合逻辑，否则 CPU 采到旧值。
// =============================================================================

`timescale 1ns / 1ps

module mvm_copro (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        valid,
    output wire        ready,
    input  wire [31:0] addr,
    input  wire [31:0] wdata,
    input  wire [ 3:0] wstrb,
    output wire [31:0] rdata,

    output wire        irq
);

// 只用 addr[7:0]：互联已经按 0x2000_xxxx 片选过了
localparam [7:0]
    OFF_CTRL    = 8'h00,
    OFF_STATUS  = 8'h04,
    OFF_IRQ     = 8'h08,
    OFF_CONFIG  = 8'h0C,
    OFF_INP     = 8'h10,
    OFF_WROW0   = 8'h20,
    OFF_WROW1   = 8'h24,
    OFF_WROW2   = 8'h28,
    OFF_WROW3   = 8'h2C,
    OFF_OUTPACK = 8'h50,
    OFF_LATENCY = 8'h54;

localparam [1:0]
    ST_IDLE   = 2'd0,
    ST_SETTLE = 2'd1,   // 等 DAC / 阵列建立
    ST_ADC    = 2'd2,   // 等 ADC 量化，最后一拍采样 y_comb
    ST_DONE   = 2'd3;   // 一拍后回到 IDLE，done/irq 保持到下次 START 或 W1C

assign ready = valid;

wire wr = valid && (|wstrb);
wire [7:0] off = addr[7:0];

reg [31:0] ctrl;
reg [31:0] cfg;
reg [31:0] xin;
reg [31:0] wrow0, wrow1, wrow2, wrow3;
reg [31:0] outpack;
reg [15:0] latency;
reg        busy;
reg        done;
reg        irq_q;
reg [1:0]  state;
reg [7:0]  cnt;

// 配 0 会卡死计数器，至少走 1 拍
wire [7:0] settle_n = (cfg[7:0]   == 8'd0) ? 8'd1 : cfg[7:0];
wire [7:0] adc_n    = (cfg[15:8]  == 8'd0) ? 8'd1 : cfg[15:8];
wire       irq_en   = ctrl[1];
// START 是写脉冲：wdata[0]=1 的那一拍启动，不锁进 ctrl
wire       start_w  = wr && (off == OFF_CTRL) && wdata[0];

wire [31:0] y_comb;
mvm_array_digital u_array (
    .xin   (xin),
    .wrow0 (wrow0),
    .wrow1 (wrow1),
    .wrow2 (wrow2),
    .wrow3 (wrow3),
    .ypack (y_comb)
);

assign irq = irq_q;

// 字节写掩码，支持 sb/sh；固件实际都是 sw
wire [31:0] wmask = {{8{wstrb[3]}}, {8{wstrb[2]}}, {8{wstrb[1]}}, {8{wstrb[0]}}};

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        ctrl    <= 32'b0;
        cfg     <= 32'h0000_0408; // adc=4, settle=8，与 socmap.SETTLE/ADC_DEFAULT 一致
        xin     <= 32'b0;
        wrow0   <= 32'b0;
        wrow1   <= 32'b0;
        wrow2   <= 32'b0;
        wrow3   <= 32'b0;
        outpack <= 32'b0;
        latency <= 16'd0;
        busy    <= 1'b0;
        done    <= 1'b0;
        irq_q   <= 1'b0;
        state   <= ST_IDLE;
        cnt     <= 8'd0;
    end else begin
        if (wr) begin
            case (off)
                OFF_CTRL: begin
                    // 只保留 IRQ_EN（bit1）；START 不存储
                    ctrl <= (ctrl & ~wmask) | (wdata & wmask & 32'h0000_0002);
                end
                OFF_IRQ: begin
                    if (wdata[0] && wstrb[0])
                        irq_q <= 1'b0;
                end
                OFF_CONFIG: cfg   <= (cfg   & ~wmask) | (wdata & wmask);
                OFF_INP:    xin   <= (xin   & ~wmask) | (wdata & wmask);
                OFF_WROW0:  wrow0 <= (wrow0 & ~wmask) | (wdata & wmask);
                OFF_WROW1:  wrow1 <= (wrow1 & ~wmask) | (wdata & wmask);
                OFF_WROW2:  wrow2 <= (wrow2 & ~wmask) | (wdata & wmask);
                OFF_WROW3:  wrow3 <= (wrow3 & ~wmask) | (wdata & wmask);
                default: ;
            endcase
        end

        case (state)
            ST_IDLE: begin
                if (start_w) begin
                    busy    <= 1'b1;
                    done    <= 1'b0;
                    irq_q   <= 1'b0;
                    cnt     <= settle_n;
                    latency <= {8'b0, settle_n} + {8'b0, adc_n} + 16'd1;
                    state   <= ST_SETTLE;
                end
            end
            ST_SETTLE: begin
                if (cnt == 8'd1) begin
                    cnt   <= adc_n;
                    state <= ST_ADC;
                end else
                    cnt <= cnt - 8'd1;
            end
            ST_ADC: begin
                if (cnt == 8'd1) begin
                    outpack <= y_comb;     // 只在这里打拍，之前组合值可以变
                    busy    <= 1'b0;
                    done    <= 1'b1;
                    irq_q   <= irq_en;
                    state   <= ST_DONE;
                end else
                    cnt <= cnt - 8'd1;
            end
            ST_DONE: begin
                state <= ST_IDLE;          // done/irq 保持，等下次 START 或 W1C
            end
            default: state <= ST_IDLE;
        endcase
    end
end

// 组合读：ready 同周期返回，CPU 的 S_MEM 才能在同一拍采到新值
reg [31:0] rdata_mux;
always @(*) begin
    case (off)
        OFF_CTRL:    rdata_mux = ctrl;
        // STATUS: bit0 busy, bit1 done, bit2 irq, [17:16] fsm
        OFF_STATUS:  rdata_mux = {14'b0, state, 13'b0, irq_q, done, busy};
        OFF_IRQ:     rdata_mux = {31'b0, irq_q};
        OFF_CONFIG:  rdata_mux = cfg;
        OFF_INP:     rdata_mux = xin;
        OFF_WROW0:   rdata_mux = wrow0;
        OFF_WROW1:   rdata_mux = wrow1;
        OFF_WROW2:   rdata_mux = wrow2;
        OFF_WROW3:   rdata_mux = wrow3;
        OFF_OUTPACK: rdata_mux = outpack;
        OFF_LATENCY: rdata_mux = {16'b0, latency};
        default:     rdata_mux = 32'b0;
    endcase
end
assign rdata = rdata_mux;

endmodule
