# =============================================================================
# 端到端固件：RISC-V 写向量 → 启动 MVM → 中断完成 → 读回 → 与黄金值比对
#
# [给你看的对照] 刚学 Python 的话：
#   本文件不是 Python。mini_asm.py 读它，编成 fw/hex/e2e_mvm.hex，再给 ISS / RTL 跑。
#   .equ NAME, 值     ≈  Python 的 NAME = 值（见 fw/python/socmap.py）
#   _start: / main:   ≈  函数入口。jal ra, run_one 相当于调用 run_one()
#   jalr zero, 0(ra)  ≈  return。ra 里装着「调用者的下一行」
#   gold_pack:        软件再算一遍 y，公式和 golden/mvm_ref.py 的 mvm_int 相同
#
# 成功判据（与题目一致）：
#   1. 每个输出 |y - y_gold| <= 1 LSB
#   2. 中断确实发生过（irq_flag 被 handler 置 1）
#   3. 向 UART 打印 PASS，向 TOHOST 写 1
#
# python scripts/sim/run_all.py 跑到 iss.py e2e_mvm.hex 时，终端对应：
#     PASS                                          ← 下面 main 末尾 putc('P','A','S','S','\n')
#     tohost=1 cycles=5658 instret=5655 irq_seen=3
#     ISS_PASS
# irq_seen=3 因为 main 只调了 3 次 run_one（zeros / fullscale / mixed）。
# identity_like 只出现在 golden/mvm_ref.py 的打印里，本固件不跑。
# cycles-instret=3：每次进 irq_handler 占 1 拍但不算指令。周期绝对值随固件变化。
# =============================================================================

.equ UART,      0x10000000
.equ MVM,       0x20000000
.equ TOHOST,    0x30000000
.equ FLAG,      0x00001F00          # irq_flag 放在 RAM 高处，避开代码

.equ MVM_CTRL,    0
.equ MVM_STATUS,  4
.equ MVM_IRQ,     8
.equ MVM_CONFIG,  12
.equ MVM_INP,     16
.equ MVM_WROW0,   32
.equ MVM_OUTPACK, 80
.equ MVM_LATENCY, 84

# ---------------- 复位向量：必须恰好填满 0x00..0x0F ----------------
_start:                             # 0x00
    lui     sp, 0x2                 # sp = 0x2000
    jal     zero, main              # 0x04
    addi    zero, zero, 0           # 0x08 nop
    addi    zero, zero, 0           # 0x0C nop

# ---------------- 机器外部中断入口 mtvec = 0x10 ----------------
irq_handler:                        # 0x10
    addi    sp, sp, -16
    sw      t0, 0(sp)
    sw      t1, 4(sp)
    lui     t0, 0x20000             # MVM base
    addi    t1, zero, 1
    sw      t1, 8(t0)               # W1C 清 IRQ
    lui     t0, 0x2
    addi    t0, t0, -256            # FLAG = 0x1F00
    addi    t1, zero, 1
    sw      t1, 0(t0)
    lw      t0, 0(sp)
    lw      t1, 4(sp)
    addi    sp, sp, 16
    mret

# ---------------- 主程序 ----------------
main:
    # 开外部中断：mie.MEIE=bit11, mstatus.MIE=bit3
    addi    t0, zero, 1
    slli    t0, t0, 11
    csrw    mie, t0
    addi    t0, zero, 8
    csrw    mstatus, t0

    # 配置 settle/adc 周期，并打开 MVM IRQ_EN
    lui     s11, 0x20000            # s11 常驻 MVM base
    addi    t0, zero, 8             # settle=8
    addi    t1, zero, 4
    slli    t1, t1, 8               # adc=4 << 8
    or      t0, t0, t1
    sw      t0, 12(s11)
    addi    t0, zero, 2             # IRQ_EN
    sw      t0, 0(s11)

    # ---- 向量 0：全 0，期望 0 ----
    addi    a0, zero, 0
    addi    a1, zero, 0
    addi    a2, zero, 0
    addi    a3, zero, 0
    addi    a4, zero, 0
    jal     ra, run_one

    # ---- 向量 1：满量程，期望 63,63,63,63 ----
    jal     ra, make_0x3f3f3f3f
    mv      a0, a0                  # x packed, already in a0
    mv      a1, a0
    mv      a2, a0
    mv      a3, a0
    mv      a4, a0
    jal     ra, run_one

    # ---- 向量 2：mixed ----
    # x = {40,50,60,63} = 0x3f3c3228
    lui     a0, 0x3f3c3
    addi    a0, a0, 0x228
    # wrow0 = {40,10,20,30} = 0x1e140a28
    lui     a1, 0x1e141
    addi    a1, a1, -1496           # 0x1e141000 - 0x5d8 = 0x1e140a28
    # 0x5d8 = 1496, 0x1e141000-1496=0x1e140a28 yes
    # wrow1 = {40,20,20,30} = 0x1e141428
    lui     a2, 0x1e141
    addi    a2, a2, 0x428
    # wrow2 = {40,30,20,30} = 0x1e141e28
    lui     a3, 0x1e142
    addi    a3, a3, -472            # 0x1e142000 - 0x1d8 = 0x1e141e28
    # wrow3 = {40,40,20,30} = 0x1e142828
    lui     a4, 0x1e142
    addi    a4, a4, 0x7FF           # 2047
    addi    a4, a4, 0x29            # 0x1e142000 + 2088 = 0x1e142828
    jal     ra, run_one

    # 全部通过。putc 写 UART_DATA=0x10000000，ISS 的 mmio_write 会立刻
    # sys.stdout.write 这些字符，所以终端先出现 "PASS" 再出现 tohost=... 行。
    # 80/65/83/83/10 = 'P' 'A' 'S' 'S' '\n'（ASCII）。
    addi    a0, zero, 80            # 'P'
    jal     ra, putc
    addi    a0, zero, 65            # 'A'
    jal     ra, putc
    addi    a0, zero, 83            # 'S'
    jal     ra, putc
    addi    a0, zero, 83            # 'S'
    jal     ra, putc
    addi    a0, zero, 10
    jal     ra, putc
    addi    a0, zero, 1             # TOHOST_PASS。ISS 看到 tohost!=0 就停
    jal     ra, write_tohost
hang:
    jal     zero, hang

fail:
    addi    a0, zero, 70            # 'F'
    jal     ra, putc
    addi    a0, zero, 10
    jal     ra, putc
    addi    a0, zero, 3
    jal     ra, write_tohost
fail_hang:
    jal     zero, fail_hang

# ---------------- 子程序 ----------------
# run_one(a0=x, a1=w0, a2=w1, a3=w2, a4=w3)
# 启动 MVM，等中断，读回，与软件黄金比对（允许 1 LSB）。
# s11 在 main 里已设为 MVM_BASE，本函数不改 s11。
run_one:
    addi    sp, sp, -32
    sw      ra, 0(sp)
    sw      a0, 4(sp)
    sw      a1, 8(sp)
    sw      a2, 12(sp)
    sw      a3, 16(sp)
    sw      a4, 20(sp)

    # 清 irq_flag
    lui     t0, 0x2
    addi    t0, t0, -256
    sw      zero, 0(t0)

    # 写寄存器
    sw      a0, 16(s11)
    sw      a1, 32(s11)
    sw      a2, 36(s11)
    sw      a3, 40(s11)
    sw      a4, 44(s11)

    # START | IRQ_EN = 3
    addi    t0, zero, 3
    sw      t0, 0(s11)

    # 等 handler 置 flag
wait_irq:
    lui     t0, 0x2
    addi    t0, t0, -256
    lw      t1, 0(t0)
    beq     t1, zero, wait_irq

    # 读结果
    lw      a5, 80(s11)             # got packed

    # 软件黄金
    lw      a0, 4(sp)
    lw      a1, 8(sp)
    lw      a2, 12(sp)
    lw      a3, 16(sp)
    lw      a4, 20(sp)
    jal     ra, gold_pack           # a0 = expected packed
    mv      a6, a0
    mv      a0, a5
    mv      a1, a6
    jal     ra, cmp4_1lsb
    beq     a0, zero, run_fail

    lw      ra, 0(sp)
    addi    sp, sp, 32
    jalr    zero, 0(ra)

run_fail:
    jal     zero, fail

# gold_pack: 输入同 run_one 的 a0..a4，返回 a0=y_packed
# 软件实现 y_j = (Σ_i x_i * W[i][j]) / 252，与 RTL 同一公式。
# 没有 mul 指令，用移位加法；除法用反复减 252。
gold_pack:
    addi    sp, sp, -48
    sw      ra, 0(sp)
    sw      s0, 4(sp)
    sw      s1, 8(sp)
    sw      s2, 12(sp)
    sw      s3, 16(sp)
    sw      s4, 20(sp)
    sw      s5, 24(sp)
    sw      s6, 28(sp)
    sw      s7, 32(sp)

    mv      s0, a0                  # x packed
    mv      s1, a1
    mv      s2, a2
    mv      s3, a3
    mv      s4, a4
    addi    s5, zero, 0             # y packed accumulator
    addi    s6, zero, 0             # j

gold_j:
    addi    s7, zero, 0             # acc
    addi    t3, zero, 0             # i
gold_i:
    # x_i
    mv      a0, s0
    mv      a1, t3
    jal     ra, extract_byte
    mv      t4, a0
    # w_ij : row i, byte j
    mv      t5, s1
    addi    t6, zero, 1
    beq     t3, t6, w_row1
    addi    t6, zero, 2
    beq     t3, t6, w_row2
    addi    t6, zero, 3
    beq     t3, t6, w_row3
    jal     zero, w_got
w_row1:
    mv      t5, s2
    jal     zero, w_got
w_row2:
    mv      t5, s3
    jal     zero, w_got
w_row3:
    mv      t5, s4
w_got:
    mv      a0, t5
    mv      a1, s6                  # byte j
    jal     ra, extract_byte
    mv      a1, a0                  # w
    mv      a0, t4                  # x
    jal     ra, mul_u
    add     s7, s7, a0              # acc += x*w
    addi    t3, t3, 1
    addi    t6, zero, 4
    blt     t3, t6, gold_i

    mv      a0, s7
    jal     ra, div252
    # insert byte j
    addi    t6, zero, 255
    and     a0, a0, t6
    slli    t0, s6, 3               # j * 8
    sll     a0, a0, t0
    or      s5, s5, a0

    addi    s6, s6, 1
    addi    t6, zero, 4
    blt     s6, t6, gold_j

    mv      a0, s5
    lw      ra, 0(sp)
    lw      s0, 4(sp)
    lw      s1, 8(sp)
    lw      s2, 12(sp)
    lw      s3, 16(sp)
    lw      s4, 20(sp)
    lw      s5, 24(sp)
    lw      s6, 28(sp)
    lw      s7, 32(sp)
    addi    sp, sp, 48
    jalr    zero, 0(ra)

# extract_byte(a0=word, a1=idx) -> a0 = (word >> (8*idx)) & 0xff
# idx 为 0..3。不保存 ra：用 jalr zero, 0(ra) 返回，调用方 jal ra, ...
extract_byte:
    slli    t0, a1, 3
    srl     a0, a0, t0
    addi    t0, zero, 255
    and     a0, a0, t0
    jalr    zero, 0(ra)

# mul_u(a0, a1) -> a0
mul_u:
    mv      t0, a0
    mv      t1, a1
    addi    a0, zero, 0
mul_loop:
    beq     t1, zero, mul_done
    andi    t2, t1, 1
    beq     t2, zero, mul_skip
    add     a0, a0, t0
mul_skip:
    slli    t0, t0, 1
    srli    t1, t1, 1
    jal     zero, mul_loop
mul_done:
    jalr    zero, 0(ra)

# div252(a0) -> a0 = a0 / 252  （商最多 63，循环可接受）
div252:
    addi    t0, zero, 0
    addi    t1, zero, 252
div_loop:
    sltu    t2, a0, t1
    bne     t2, zero, div_done
    sub     a0, a0, t1
    addi    t0, t0, 1
    jal     zero, div_loop
div_done:
    mv      a0, t0
    jalr    zero, 0(ra)

# cmp4_1lsb(a0=got, a1=exp) -> a0=1 pass, 0 fail
# 四个字节各自 |got-exp| < 2，即题目的 ≤ 1 LSB。
cmp4_1lsb:
    addi    sp, sp, -16
    sw      ra, 0(sp)
    addi    t3, zero, 0             # idx
cmp_i:
    addi    sp, sp, -8
    sw      a0, 0(sp)
    sw      a1, 4(sp)
    mv      a1, t3
    jal     ra, extract_byte        # got byte, but a0 was got word — saved
    mv      t4, a0
    lw      a0, 4(sp)
    mv      a1, t3
    jal     ra, extract_byte
    mv      t5, a0
    lw      a0, 0(sp)
    lw      a1, 4(sp)
    addi    sp, sp, 8
    sub     t4, t4, t5
    blt     t4, zero, cmp_neg
    jal     zero, cmp_abs
cmp_neg:
    sub     t4, zero, t4
cmp_abs:
    addi    t5, zero, 2
    sltu    t5, t4, t5              # abs < 2
    beq     t5, zero, cmp_fail
    addi    t3, t3, 1
    addi    t5, zero, 4
    blt     t3, t5, cmp_i
    addi    a0, zero, 1
    lw      ra, 0(sp)
    addi    sp, sp, 16
    jalr    zero, 0(ra)
cmp_fail:
    addi    a0, zero, 0
    lw      ra, 0(sp)
    addi    sp, sp, 16
    jalr    zero, 0(ra)

make_0x3f3f3f3f:
    addi    a0, zero, 63
    slli    t0, a0, 8
    or      a0, a0, t0
    slli    t0, a0, 16
    or      a0, a0, t0
    jalr    zero, 0(ra)

putc:
    # ISS 见到写 0x10000000 低字节，就把 a0 当 ASCII 打到终端（见 iss.py mmio_write）
    lui     t0, 0x10000
    sw      a0, 0(t0)
    jalr    zero, 0(ra)

write_tohost:
    # ISS 见到写 0x30000000 就把 tohost 设成 a0，run() 循环结束，打印 tohost=...
    lui     t0, 0x30000
    sw      a0, 0(t0)
    jalr    zero, 0(ra)
