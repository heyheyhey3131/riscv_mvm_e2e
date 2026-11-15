#include "mvm_hw.h"   /* 把 mvm_hw.h 里的 #define 和内联函数粘进来，类似 Python 的 from socmap import ... */

/* 可读的 C 版端到端程序。需要 riscv32-unknown-elf-gcc（-march=rv32i_zicsr）。
 * 日常仿真请用 fw/asm/e2e_mvm.S + mini_asm.py，不必装交叉编译器。
 *
 * [给你看的对照] 刚学 Python 的话：
 *   #include "mvm_hw.h"     ≈  from socmap import MVM_BASE, pack4, ...
 *   static unsigned mulu()  ≈  def mulu(...)，static 表示只给本文件用
 *   unsigned / int          必须写类型；Python 不用写，运行时自己认
 *   while (*s)              *s 是指针解引用：取出 s 指向的那个字符
 *   gold_pack / cmp4_1lsb   和汇编版、mvm_ref.py 的 mvm_int 是同一套公式
 */

/* C 版必须自己开机器外部中断；否则 run_one() 等 0x1F00 会永远等不到。
 * 汇编版在 e2e_mvm.S 的 main 里用 csrw 做了同样的事。
 * 这里把 CSR 号直接写成立即数，避免函数参数不能作为 "i" 约束的问题。 */
static inline void enable_machine_irq(void)
{
    unsigned meie = 1u << 11;
    unsigned mie  = 1u << 3;
    __asm__ volatile ("csrw 0x304, %0" :: "r"(meie) : "memory");
    __asm__ volatile ("csrw 0x300, %0" :: "r"(mie) : "memory");
}

static void putc_uart(char c)
{
    mmio_write(UART_DATA, (unsigned)c);
}

static void puts_uart(const char *s)
{
    while (*s)
        putc_uart(*s++);
}

/* RV32I 没有 mul：用移位加法。6-bit × 6-bit 最多十几轮。 */
static unsigned mulu(unsigned a, unsigned b)
{
    unsigned r = 0;
    while (b) {
        if (b & 1u)
            r += a;
        a <<= 1;
        b >>= 1;
    }
    return r;
}

static unsigned div252(unsigned acc)
{
    unsigned q = 0;
    while (acc >= MVM_SCALE) {
        acc -= MVM_SCALE;
        q++;
    }
    return q;
}

static unsigned extract_byte(unsigned word, unsigned idx)
{
    return (word >> (8u * idx)) & 0xffu;
}

static unsigned gold_pack(unsigned x, unsigned w0, unsigned w1, unsigned w2, unsigned w3)
{
    unsigned y = 0;
    unsigned wrow[4];
    unsigned j, i;
    wrow[0] = w0;
    wrow[1] = w1;
    wrow[2] = w2;
    wrow[3] = w3;
    for (j = 0; j < 4; j++) {
        unsigned acc = 0;
        for (i = 0; i < 4; i++) {
            unsigned xv = extract_byte(x, i);
            unsigned wv = extract_byte(wrow[i], j);
            acc += mulu(xv, wv);
        }
        y |= (div252(acc) & 0xffu) << (8u * j);
    }
    return y;
}

static int cmp4_1lsb(unsigned got, unsigned exp)
{
    unsigned i;
    for (i = 0; i < 4; i++) {
        int a = (int)extract_byte(got, i);
        int b = (int)extract_byte(exp, i);
        int d = a - b;
        if (d < 0)
            d = -d;
        if (d > 1)
            return 0;
    }
    return 1;
}

/* 写寄存器、发 START、忙等 0x1F00。进入本函数前必须已经 enable_machine_irq()。 */
static unsigned run_one(unsigned x, unsigned w0, unsigned w1, unsigned w2, unsigned w3)
{
    volatile unsigned *flag = (volatile unsigned *)0x00001F00u;
    *flag = 0;
    mmio_write(MVM_INP, x);
    mmio_write(MVM_WROW0, w0);
    mmio_write(MVM_WROW1, w1);
    mmio_write(MVM_WROW2, w2);
    mmio_write(MVM_WROW3, w3);
    mmio_write(MVM_CTRL, MVM_CTRL_START | MVM_CTRL_IRQ_EN);
    while (*flag == 0)
        ;
    return mmio_read(MVM_OUTPACK);
}

int main(void)
{
    unsigned got, exp;

    /* mie.MEIE, mstatus.MIE — 与汇编版 main 相同 */
    enable_machine_irq();

    mmio_write(MVM_CONFIG, (unsigned)MVM_SETTLE_DEFAULT | ((unsigned)MVM_ADC_DEFAULT << 8));
    mmio_write(MVM_CTRL, MVM_CTRL_IRQ_EN);

    got = run_one(0, 0, 0, 0, 0);
    exp = gold_pack(0, 0, 0, 0, 0);
    if (!cmp4_1lsb(got, exp))
        goto fail;

    got = run_one(0x3f3f3f3fu, 0x3f3f3f3fu, 0x3f3f3f3fu, 0x3f3f3f3fu, 0x3f3f3f3fu);
    exp = gold_pack(0x3f3f3f3fu, 0x3f3f3f3fu, 0x3f3f3f3fu, 0x3f3f3f3fu, 0x3f3f3f3fu);
    if (!cmp4_1lsb(got, exp))
        goto fail;

    got = run_one(0x3f3c3228u, 0x1e140a28u, 0x1e141428u, 0x1e141e28u, 0x1e142828u);
    exp = gold_pack(0x3f3c3228u, 0x1e140a28u, 0x1e141428u, 0x1e141e28u, 0x1e142828u);
    if (!cmp4_1lsb(got, exp))
        goto fail;

    puts_uart("PASS\n");
    mmio_write(TOHOST_BASE, TOHOST_PASS);
    for (;;)
        ;
fail:
    puts_uart("FAIL\n");
    mmio_write(TOHOST_BASE, TOHOST_FAIL);
    for (;;)
        ;
}
