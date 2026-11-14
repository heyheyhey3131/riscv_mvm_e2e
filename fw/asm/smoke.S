# 最小冒烟：不碰 MVM，只验证 CPU 能取指、写 MMIO。
# 成功：向 TOHOST 写入 1。
#
# python scripts/sim/run_all.py 跑到 iss.py smoke.hex 时，终端对应：
#     tohost=1 cycles=3 instret=3 irq_seen=0
#     ISS_PASS
# 三条指令：lui → addi → sw。sw 把 0x30000000 写成 1 后 ISS 停机，
# hang 的 jal 不会被执行，所以 cycles=3 而不是无限循环。
# 没有 UART 输出，因此这里看不到 PASS（PASS 是 e2e_mvm.S 打的）。
#
# [给你看的对照] 刚学 Python 的话：
#   这里没有 def / class / import。一行就是 CPU 要执行的一条指令。
#   _start: / hang:     标签，相当于函数名或 goto 的落点
#   .equ TOHOST, ...    给数字起名，相当于 Python 的 TOHOST = 0x30000000
#   lui / addi / sw     真正的机器指令，mini_asm.py 会把它们编成 32-bit 数
#
# lui 的立即数是高 20 位：0x30000 << 12 = 0x30000000。
# jal zero, hang 编码成无条件跳转，不停写 tohost。

.equ TOHOST, 0x30000000

_start:
    lui     t0, 0x30000          # t0 = 0x30000000
    addi    t1, zero, 1
    sw      t1, 0(t0)
hang:
    jal     zero, hang
