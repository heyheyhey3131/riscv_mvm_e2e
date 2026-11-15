#ifndef MVM_HW_H
#define MVM_HW_H

/*
 * C 固件看到的硬件地图。
 * 必须与 rtl/include/soc_cfg.vh、fw/python/socmap.py 保持一致。
 * 没有 RISC-V GCC 时本文件只作阅读对照；真正仿真走 fw/asm/e2e_mvm.S。
 *
 * [给你看的对照] 刚学 Python 的话：
 *   本文件 ≈ fw/python/socmap.py 的 C 语言翻译。
 *   #define MVM_BASE 0x20000000u   ≈  Python 的 MVM_BASE = 0x20000000
 *   #ifndef / #define / #endif     头文件卫士：同一个 .h 被 include 两次也不重复定义
 *   static inline mmio_write()     内联小函数，≈ def mmio_write(addr, value)
 *   volatile                       告诉编译器「这是硬件寄存器，每次都要真的读/写，别优化掉」
 */

/* ---- 存储与启动 ---- */
#define RAM_BASE      0x00000000u
#define RAM_BYTES     8192u
#define RAM_WORDS     (RAM_BYTES / 4u)     /* 2048 个 32-bit 字 */
#define RESET_PC      0x00000000u
#define STACK_TOP     0x00002000u         /* sp 初值，栈向低地址增长 */
#define MTVEC_RESET   0x00000010u         /* 中断入口，固件用 nop 填满 0x00..0x0F */

/* ---- UART：教学用只发不收。TB 会监听 DATA 写并 $write 字符 ---- */
#define UART_BASE     0x10000000u
#define UART_DATA     (UART_BASE + 0x0u)
#define UART_STATUS   (UART_BASE + 0x4u)

/* ---- MVM 协处理器 MMIO，字对齐 ---- */
#define MVM_BASE      0x20000000u
#define MVM_CTRL      (MVM_BASE + 0x00u)  /* 写 START 是脉冲，不占用存储位 */
#define MVM_STATUS    (MVM_BASE + 0x04u)  /* [0] BUSY [1] DONE [2] IRQ [17:16] FSM */
#define MVM_IRQ       (MVM_BASE + 0x08u)  /* 写 1 清除 irq 电平 */
#define MVM_CONFIG    (MVM_BASE + 0x0Cu)
#define MVM_INP       (MVM_BASE + 0x10u)  /* 小端：byte0 = x0 */
#define MVM_WROW0     (MVM_BASE + 0x20u)  /* WROW_i 的 byte_j = W[i][j] */
#define MVM_WROW1     (MVM_BASE + 0x24u)
#define MVM_WROW2     (MVM_BASE + 0x28u)
#define MVM_WROW3     (MVM_BASE + 0x2Cu)
#define MVM_OUTPACK   (MVM_BASE + 0x50u)
#define MVM_LATENCY   (MVM_BASE + 0x54u)

#define TOHOST_BASE   0x30000000u

#define MVM_CTRL_START   (1u << 0)
#define MVM_CTRL_IRQ_EN  (1u << 1)

#define MVM_ST_BUSY      (1u << 0)
#define MVM_ST_DONE      (1u << 1)
#define MVM_ST_IRQ       (1u << 2)

#define MVM_N            4
#define MVM_BITS         6
#define MVM_MAX          63
#define MVM_SCALE        252              /* y = sum(x*w) / 252 */
#define MVM_SETTLE_DEFAULT 8              /* 与 rtl 的 MVM_SETTLE_DFLT 一致 */
#define MVM_ADC_DEFAULT    4              /* 与 rtl 的 MVM_ADC_DFLT 一致 */

#define TOHOST_PASS      1u
#define TOHOST_FAIL      3u

/* 无缓存、无写缓冲：每次访问都是一次总线事务 */
static inline void mmio_write(unsigned addr, unsigned value)
{
    *(volatile unsigned *)addr = value;
}

static inline unsigned mmio_read(unsigned addr)
{
    return *(volatile unsigned *)addr;
}

/* 小端打包 4 个字节。MVM 的 x / W 行 / y 都用这个布局。 */
static inline unsigned pack4(unsigned b0, unsigned b1, unsigned b2, unsigned b3)
{
    return (b0 & 0xffu)
         | ((b1 & 0xffu) << 8)
         | ((b2 & 0xffu) << 16)
         | ((b3 & 0xffu) << 24);
}

#endif
