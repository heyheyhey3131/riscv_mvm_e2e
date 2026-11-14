# GCC 启动文件（可选）。没有 RISC-V GCC 时请用 fw/asm + mini_asm.py。
# 布局必须和 e2e_mvm.S 一样：0x00 复位，0x10 中断。需要 zicsr 才认 mret。
# 编译：见 fw/Makefile。中断使能仍在 C 的 main 之前——本文件只设 sp 并跳 main。
#
# [给你看的对照] 刚学 Python 的话：
#   这是给 C 版固件用的「启动代码」，角色像 Python 的 if __name__ == "__main__": main()
#   CPU 上电从 _start 取指，设好栈指针 sp，再跳到 C 的 main。
#   .globl _start  让链接器找得到这个名字；.extern main 表示 main 定义在别的文件。

    .section .text
    .globl _start
    .globl irq_handler
    .extern main

_start:
    lui     sp, 0x2
    j       main
    nop
    nop

    .align 4
irq_handler:
    addi    sp, sp, -16
    sw      t0, 0(sp)
    sw      t1, 4(sp)
    lui     t0, 0x20000
    li      t1, 1
    sw      t1, 8(t0)
    lui     t0, 0x2
    addi    t0, t0, -256
    li      t1, 1
    sw      t1, 0(t0)
    lw      t0, 0(sp)
    lw      t1, 4(sp)
    addi    sp, sp, 16
    mret
