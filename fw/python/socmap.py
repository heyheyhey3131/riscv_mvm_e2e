"""SoC 地址与量化常量（Python 侧唯一副本）。

本文件是一个模块：没有 if __name__ == "__main__"，从不单独跑。
给 mini_asm.py、iss.py、golden/mvm_ref.py 用——他们 from socmap import XXX。

必须与 rtl/include/soc_cfg.vh、fw/include/mvm_hw.h 保持一致。
改地址时三处一起改，否则 ISS 能过、RTL 会挂（或反过来）。

语法对照（相对 C）：
  NAME = 值          模块级常量。Python 没有 const，约定全大写就是别改
  0x20000000         十六进制整数，和 C 的 0x20000000 同一个数
  1 << 0             左移，和 C 完全一样
  a // b             整数除法（C 里两个 int 的 /）
  def pack4(a,b,c,d) 函数；不用写类型，return 什么就是什么
"""

# ---- 存储 ----
RAM_BASE = 0x00000000
RAM_BYTES = 8192
RAM_WORDS = RAM_BYTES // 4          # // 整数除法。8192/4=2048 个 32-bit 字
STACK_TOP = 0x00002000              # 复位后固件 lui sp, 2 得到这个值
RESET_PC = 0x00000000
MTVEC = 0x00000010                  # 机器外部中断入口，固件 irq_handler 必须落在这

# ---- UART ----
UART_BASE = 0x10000000
UART_DATA = UART_BASE + 0x0         # 写低 8 位发送；ISS 会把字符打印到 stdout
UART_STATUS = UART_BASE + 0x4

# ---- MVM 协处理器 ----
MVM_BASE = 0x20000000
MVM_CTRL = MVM_BASE + 0x00
MVM_STATUS = MVM_BASE + 0x04
MVM_IRQ = MVM_BASE + 0x08
MVM_CONFIG = MVM_BASE + 0x0C
MVM_INP = MVM_BASE + 0x10
# 列表推导：[表达式 for i in range(4)]
# 相当于 C:
#   int MVM_WROW[4];
#   for (i = 0; i < 4; i++) MVM_WROW[i] = MVM_BASE + 0x20 + 4 * i;
# 结果：[0x20000020, 0x20000024, 0x20000028, 0x2000002C]
MVM_WROW = [MVM_BASE + 0x20 + 4 * i for i in range(4)]
MVM_WROW0 = MVM_WROW[0]
MVM_WROW1 = MVM_WROW[1]
MVM_WROW2 = MVM_WROW[2]
MVM_WROW3 = MVM_WROW[3]
MVM_OUTPACK = MVM_BASE + 0x50
MVM_LATENCY = MVM_BASE + 0x54

TOHOST_BASE = 0x30000000

# CTRL / STATUS 位定义，与 RTL mvm_copro.v 对齐
# 1 << n  把 1 往左挪 n 位。1<<0=1, 1<<1=2, 1<<2=4。和 C 一样。
MVM_CTRL_START = 1 << 0             # 写 1 启动一次运算，硬件不锁存这一位
MVM_CTRL_IRQ_EN = 1 << 1            # 1 = DONE 时拉 irq

MVM_ST_BUSY = 1 << 0
MVM_ST_DONE = 1 << 1
MVM_ST_IRQ = 1 << 2

MVM_N = 4
MVM_BITS = 6
MVM_MAX = 63
MVM_SCALE = 252  # 4 * 63 * 63 / 63，满量程映射到 63

TOHOST_PASS = 1
TOHOST_FAIL = 3

# 与 RTL 复位默认 cfg = 0x0000_0408 相同
SETTLE_DEFAULT = 8
ADC_DEFAULT = 4


def pack4(b0, b1, b2, b3):
    """小端：byte0 在最低字节。x0 / W[i][0] / y0 都走这一路。

    四个位置参数，按顺序传入。调用 pack4(10, 20, 30, 40) 时：
        b0=10, b1=20, b2=30, b3=40
    & 0xFF 只留低 8 位；<< 8 把数字挪到下一个字节的位置。
    | 按位或，把四个字节拼成一个 32-bit 整数。和 C 完全一样。
    """
    return (b0 & 0xFF) | ((b1 & 0xFF) << 8) | ((b2 & 0xFF) << 16) | ((b3 & 0xFF) << 24)


def unpack4(word):
    """pack4 的逆操作，ISS 算 MVM 前要把寄存器拆成 4 个 6-bit 码。

    return [a, b, c, d]  返回一个 4 个数的 list，不是 C 那种通过指针输出。
    调用方：  bytes = unpack4(word)   然后 bytes[0] 就是最低字节。
    """
    return [word & 0xFF, (word >> 8) & 0xFF, (word >> 16) & 0xFF, (word >> 24) & 0xFF]
