// =============================================================================
// rv32i_min — 可读的多周期 RV32I 小核
//
// [给你看的对照] 刚学 Python 的话：
//   本模块 ≈ scripts/sim/iss.py 里的 class ISS，但这里是真硬件、按时钟拍走。
//   state = S_FETCH/DECODE/EXEC/...   ≈  ISS.step() 里「取指 → 译码 → 执行」拆成多拍
//   mem_valid / mem_ready             CPU 和总线的握手：我请求，你应答
//
// 总线协议与 PicoRV32 native memory interface 相同：
//   mem_valid 保持到 mem_ready；读时 mem_wstrb=0；写时 mem_wstrb 为字节使能。
//
// 为什么用多周期而不是直接例化 PicoRV32：
//   1. 源码短，每条指令的取指/译码/执行/访存/写回都能在波形里看到
//   2. 中断走标准 mstatus/mie/mepc/mret，方便对照 RISC-V 手册
//   3. 需要时可用 third_party 的 PicoRV32 按同一总线替换（见 third_party/README.md）
// =============================================================================

`timescale 1ns / 1ps

module rv32i_min #(
    parameter [31:0] RESET_PC = 32'h0000_0000,  // 复位 PC，本 SoC 为 0
    parameter [31:0] MTVEC    = 32'h0000_0010   // 中断向量，固件 irq_handler 必须对准
) (
    input  wire        clk,
    input  wire        rst_n,

    output wire        mem_valid,   // 1 表示正在做一次总线事务
    output wire        mem_instr,   // 1 = 取指（互联不区分，仅观察）
    input  wire        mem_ready,   // 从设备应答；valid 保持到 ready
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [ 3:0] mem_wstrb,   // 0=读；非 0=按字节写
    input  wire [31:0] mem_rdata,

    input  wire        irq          // 电平敏感，接到 mvm_copro.irq
);

// 多周期：每条指令在波形上能数拍。LOAD/STORE 多走 S_MEM。
localparam [2:0]
    S_FETCH  = 3'd0,
    S_DECODE = 3'd1,
    S_EXEC   = 3'd2,
    S_MEM    = 3'd3,
    S_WB     = 3'd4,
    S_IRQ    = 3'd5;

reg  [2:0]  state;
reg  [31:0] pc;
reg  [31:0] ir;
reg  [31:0] rs1_v, rs2_v;
reg  [31:0] alu_r;
reg  [31:0] load_r;
reg         br_taken;
reg  [31:0] pc_nxt;

reg  [31:0] mstatus;
reg  [31:0] mie;
reg  [31:0] mepc;
reg  [31:0] mcause;
reg  [31:0] mscratch;

reg  [31:0] rf [0:31];          // x0 恒 0：写回时 rd==0 则不写，读时旁路 0

// RISC-V 指令字段。ir 在 S_FETCH 采到后整条指令周期内保持不变。
wire [4:0] rd    = ir[11:7];
wire [4:0] rs1   = ir[19:15];
wire [4:0] rs2   = ir[24:20];
wire [2:0] funct3= ir[14:12];
wire [6:0] funct7= ir[31:25];
wire [6:0] opcode= ir[6:0];

// 立即数符号扩展。B/J 的最低位硬件补 0，保证 2 字节对齐。
wire [31:0] imm_i = {{20{ir[31]}}, ir[31:20]};
wire [31:0] imm_s = {{20{ir[31]}}, ir[31:25], ir[11:7]};
wire [31:0] imm_b = {{19{ir[31]}}, ir[31], ir[7], ir[30:25], ir[11:8], 1'b0};
wire [31:0] imm_u = {ir[31:12], 12'b0};
wire [31:0] imm_j = {{11{ir[31]}}, ir[31], ir[19:12], ir[20], ir[30:21], 1'b0};

wire is_load  = (opcode == 7'b0000011);
wire is_store = (opcode == 7'b0100011);
wire is_sys   = (opcode == 7'b1110011);

// 只在指令边界（FETCH）采样。mstatus.MIE=bit3，mie.MEIE=bit11。
wire irq_take = irq && mstatus[3] && mie[11];

// 进中断时不发起取指，避免和 S_IRQ 写 mepc 抢总线
assign mem_valid = ((state == S_FETCH) && !irq_take) || (state == S_MEM);
assign mem_instr = (state == S_FETCH);
assign mem_addr  = (state == S_FETCH) ? pc : alu_r;
assign mem_wstrb = (state == S_MEM && is_store) ? store_strb : 4'b0000;
assign mem_wdata = store_data;

wire [1:0]  addr2 = alu_r[1:0];
reg  [3:0]  store_strb;
reg  [31:0] store_data;

// 存储：把 rs2 复制到对应字节通道，SRAM 按 wstrb 写入
always @(*) begin
    store_strb = 4'b0000;
    store_data = 32'b0;
    case (funct3)
        3'b000: begin                          // sb
            store_strb = 4'b0001 << addr2;
            store_data = {4{rs2_v[7:0]}};
        end
        3'b001: begin                          // sh，要求 addr[0]==0
            store_strb = addr2[1] ? 4'b1100 : 4'b0011;
            store_data = {2{rs2_v[15:0]}};
        end
        default: begin                         // sw
            store_strb = 4'b1111;
            store_data = rs2_v;
        end
    endcase
end

// 加载：先按地址右移对齐，再符号/零扩展
wire [31:0] load_shift = load_r >> {addr2, 3'b000};
reg  [31:0] load_ext;
always @(*) begin
    case (funct3)
        3'b000:  load_ext = {{24{load_shift[7]}},  load_shift[7:0]};  // lb
        3'b001:  load_ext = {{16{load_shift[15]}}, load_shift[15:0]}; // lh
        3'b100:  load_ext = {24'b0, load_shift[7:0]};                 // lbu
        3'b101:  load_ext = {16'b0, load_shift[15:0]};                // lhu
        default: load_ext = load_r;                                   // lw
    endcase
end

wire [31:0] shamt = {27'b0, (opcode == 7'b0010011) ? ir[24:20] : rs2_v[4:0]};

reg  [31:0] alu_a, alu_b, alu_y;
reg  [3:0]  alu_op;

localparam [3:0]
    ALU_ADD  = 4'd0,
    ALU_SUB  = 4'd1,
    ALU_AND  = 4'd2,
    ALU_OR   = 4'd3,
    ALU_XOR  = 4'd4,
    ALU_SLL  = 4'd5,
    ALU_SRL  = 4'd6,
    ALU_SRA  = 4'd7,
    ALU_SLT  = 4'd8,
    ALU_SLTU = 4'd9;

always @(*) begin
    case (alu_op)
        ALU_ADD:  alu_y = alu_a + alu_b;
        ALU_SUB:  alu_y = alu_a - alu_b;
        ALU_AND:  alu_y = alu_a & alu_b;
        ALU_OR:   alu_y = alu_a | alu_b;
        ALU_XOR:  alu_y = alu_a ^ alu_b;
        ALU_SLL:  alu_y = alu_a << alu_b[4:0];
        ALU_SRL:  alu_y = alu_a >> alu_b[4:0];
        ALU_SRA:  alu_y = $unsigned($signed(alu_a) >>> alu_b[4:0]); // 算术右移后收回无符号线网
        ALU_SLT:  alu_y = ($signed(alu_a) < $signed(alu_b)) ? 32'd1 : 32'd0;
        ALU_SLTU: alu_y = (alu_a < alu_b) ? 32'd1 : 32'd0;          // 无符号，sltiu 的 imm 已符号扩展再当无符号比
        default:  alu_y = 32'd0;
    endcase
end

always @(*) begin
    alu_a  = rs1_v;
    alu_b  = rs2_v;
    alu_op = ALU_ADD;
    // 按 opcode 选 ALU 输入。LUI 当成 0+imm_u；分支在这里只算目标地址。
    case (opcode)
        7'b0110111: begin alu_a = 32'b0; alu_b = imm_u; alu_op = ALU_ADD; end // LUI
        7'b0010111: begin alu_a = pc;    alu_b = imm_u; alu_op = ALU_ADD; end // AUIPC
        7'b1101111: begin alu_a = pc;    alu_b = imm_j; alu_op = ALU_ADD; end // JAL
        7'b1100111: begin alu_a = rs1_v; alu_b = imm_i; alu_op = ALU_ADD; end // JALR
        7'b1100011: begin alu_a = pc;    alu_b = imm_b; alu_op = ALU_ADD; end // BR tgt
        7'b0000011: begin alu_a = rs1_v; alu_b = imm_i; alu_op = ALU_ADD; end
        7'b0100011: begin alu_a = rs1_v; alu_b = imm_s; alu_op = ALU_ADD; end
        7'b0010011: begin
            alu_a = rs1_v;
            alu_b = (funct3 == 3'b001 || funct3 == 3'b101) ? shamt : imm_i;
            case (funct3)
                3'b000: alu_op = ALU_ADD;
                3'b010: alu_op = ALU_SLT;
                3'b011: alu_op = ALU_SLTU;
                3'b100: alu_op = ALU_XOR;
                3'b110: alu_op = ALU_OR;
                3'b111: alu_op = ALU_AND;
                3'b001: alu_op = ALU_SLL;
                3'b101: alu_op = ir[30] ? ALU_SRA : ALU_SRL;
                default: alu_op = ALU_ADD;
            endcase
        end
        7'b0110011: begin
            alu_a = rs1_v;
            alu_b = (funct3 == 3'b001 || funct3 == 3'b101) ? shamt : rs2_v;
            case (funct3)
                3'b000: alu_op = ir[30] ? ALU_SUB : ALU_ADD;
                3'b010: alu_op = ALU_SLT;
                3'b011: alu_op = ALU_SLTU;
                3'b100: alu_op = ALU_XOR;
                3'b110: alu_op = ALU_OR;
                3'b111: alu_op = ALU_AND;
                3'b001: alu_op = ALU_SLL;
                3'b101: alu_op = ir[30] ? ALU_SRA : ALU_SRL;
                default: alu_op = ALU_ADD;
            endcase
        end
        default: begin
            alu_a  = rs1_v;
            alu_b  = rs2_v;
            alu_op = ALU_ADD;
        end
    endcase
end

wire eq  = (rs1_v == rs2_v);
wire lt  = ($signed(rs1_v) < $signed(rs2_v));
wire ltu = (rs1_v < rs2_v);

reg take_br;
always @(*) begin
    case (funct3)
        3'b000:  take_br = eq;
        3'b001:  take_br = ~eq;
        3'b100:  take_br = lt;
        3'b101:  take_br = ~lt;
        3'b110:  take_br = ltu;
        3'b111:  take_br = ~ltu;
        default: take_br = 1'b0;
    endcase
end

// 只实现固件用到的那几个机器模式 CSR，不是完整特权态
wire [11:0] csr_addr = ir[31:20];
reg  [31:0] csr_rdata;
always @(*) begin
    case (csr_addr)
        12'h300: csr_rdata = mstatus;
        12'h304: csr_rdata = mie;
        12'h305: csr_rdata = MTVEC;                 // 只读，写被忽略
        12'h340: csr_rdata = mscratch;
        12'h341: csr_rdata = mepc;
        12'h342: csr_rdata = mcause;
        12'h344: csr_rdata = {20'b0, irq, 11'b0};  // mip.MEIP = bit11，随 irq 电平
        default: csr_rdata = 32'b0;
    endcase
end

// funct3[2]=1 表示立即数 CSR（csrrwi 等），源是 rs1 字段本身不是寄存器值
wire [31:0] csr_src = ir[14] ? {27'b0, rs1} : rs1_v;
reg  [31:0] csr_wdata;
always @(*) begin
    case (funct3[1:0])
        2'b01:   csr_wdata = csr_src;              // CSRRW / CSRRWI
        2'b10:   csr_wdata = csr_rdata | csr_src;  // CSRRS
        2'b11:   csr_wdata = csr_rdata & ~csr_src; // CSRRC
        default: csr_wdata = csr_rdata;
    endcase
end

// CSRRS/CSRRC 且 rs1=x0 是纯读，不写 CSR
wire csr_we = is_sys && (funct3 != 3'b000) &&
              !((funct3[1:0] != 2'b01) && (rs1 == 5'd0));

wire is_mret = (ir == 32'h30200073);
// 分支、store、ecall/mret/wfi 不写 rd；x0 永远不写
wire we_rd   = (rd != 5'd0) &&
               (opcode != 7'b1100011) &&
               (opcode != 7'b0100011) &&
               !(is_sys && funct3 == 3'b000);

reg  [31:0] wb_data;
always @(*) begin
    wb_data = alu_r;
    if (is_load)
        wb_data = load_ext;
    else if (opcode == 7'b1101111 || opcode == 7'b1100111)
        wb_data = pc + 32'd4;
    else if (is_sys && funct3 != 3'b000)
        wb_data = csr_rdata;
end

integer i;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        state    <= S_FETCH;
        pc       <= RESET_PC;
        ir       <= 32'b0;
        rs1_v    <= 32'b0;
        rs2_v    <= 32'b0;
        alu_r    <= 32'b0;
        load_r   <= 32'b0;
        br_taken <= 1'b0;
        pc_nxt   <= RESET_PC;
        mstatus  <= 32'b0;
        mie      <= 32'b0;
        mepc     <= 32'b0;
        mcause   <= 32'b0;
        mscratch <= 32'b0;
        for (i = 0; i < 32; i = i + 1)
            rf[i] <= 32'b0;
    end else begin
        case (state)
            S_FETCH: begin
                if (irq_take) begin
                    state <= S_IRQ;                 // 当前 PC 还没取指，作为返回地址
                end else if (mem_ready) begin
                    ir    <= mem_rdata;
                    state <= S_DECODE;
                end
            end

            S_DECODE: begin
                rs1_v <= (rs1 == 5'd0) ? 32'b0 : rf[rs1];
                rs2_v <= (rs2 == 5'd0) ? 32'b0 : rf[rs2];
                state <= S_EXEC;
            end

            S_EXEC: begin
                alu_r    <= alu_y;
                br_taken <= (opcode == 7'b1100011) && take_br;
                if (opcode == 7'b1101111)
                    pc_nxt <= alu_y;                // JAL：pc + imm_j
                else if (opcode == 7'b1100111)
                    pc_nxt <= alu_y & ~32'd1;       // JALR：清 bit0
                else if (opcode == 7'b1100011)
                    pc_nxt <= take_br ? alu_y : (pc + 32'd4);
                else if (is_mret)
                    pc_nxt <= mepc;
                else
                    pc_nxt <= pc + 32'd4;

                if (is_sys && funct3 != 3'b000 && csr_we) begin
                    case (csr_addr)
                        12'h300: mstatus  <= csr_wdata;
                        12'h304: mie      <= csr_wdata;
                        12'h340: mscratch <= csr_wdata;
                        12'h341: mepc     <= csr_wdata;
                        12'h342: mcause   <= csr_wdata;
                        default: ;
                    endcase
                end
                if (is_mret) begin
                    mstatus[3] <= mstatus[7];       // MIE <- MPIE
                    mstatus[7] <= 1'b1;             // MPIE <- 1
                end

                if (is_load || is_store)
                    state <= S_MEM;
                else
                    state <= S_WB;
            end

            S_MEM: begin
                if (mem_ready) begin
                    load_r <= mem_rdata;
                    state  <= S_WB;
                end
            end

            S_WB: begin
                if (we_rd)
                    rf[rd] <= wb_data;
                pc    <= pc_nxt;
                state <= S_FETCH;
            end

            S_IRQ: begin
                mepc       <= pc;                   // 尚未执行的那条指令
                mcause     <= 32'd11;               // 机器外部中断（简化：不置 bit31）
                mstatus[7] <= mstatus[3];           // 保存 MIE
                mstatus[3] <= 1'b0;                 // 关中断，handler 里不会嵌套
                pc         <= MTVEC;
                state      <= S_FETCH;
            end

            default: state <= S_FETCH;
        endcase
    end
end

endmodule
