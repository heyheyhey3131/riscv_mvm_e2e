#!/usr/bin/env python3
"""RV32I + MVM 协处理器指令集仿真器（ISS）。

本文件是模块：用纯 Python 解释每一条 32-bit 指令，不依赖 Verilog 仿真器。
class ISS ≈ 一颗 CPU；class MvmModel ≈ 协处理器。step() 每调用一次执行一条指令。

不依赖 Verilog 仿真器，用来：
  1. 验证固件算法
  2. 作为 RTL 仿真的对照黄金 CPU
  3. Windows 上零 EDA 环境的第一站

中断模型与 RTL 对齐：
  - 指令边界采样 irq
  - mstatus.MIE (bit3)、mie.MEIE (bit11)
  - mtvec 固定 0x10，mret 恢复
"""

import argparse
import json
import sys
from pathlib import Path

# 本文件在 <root>/scripts/sim/ → parents[2] = 仓库根
ROOT = Path(__file__).resolve().parents[2]
# 两个目录都要进 sys.path，才能 from socmap import / from mvm_ref import
sys.path.insert(0, str(ROOT / "fw" / "python"))
sys.path.insert(0, str(ROOT / "golden"))

# 括号里列出一长串名字：一次 from 多个常量。每个名字对应 socmap.py 里的同名变量。
# 换行只是为了好读，和写成一行 from socmap import A, B, C 意思一样。
from socmap import (  # noqa: E402
    ADC_DEFAULT,
    MVM_BASE,
    MVM_CONFIG,
    MVM_CTRL,
    MVM_CTRL_IRQ_EN,
    MVM_CTRL_START,
    MVM_INP,
    MVM_IRQ,
    MVM_LATENCY,
    MVM_OUTPACK,
    MVM_SCALE,
    MVM_ST_BUSY,
    MVM_ST_DONE,
    MVM_ST_IRQ,
    MVM_STATUS,
    MVM_WROW,
    RAM_BYTES,
    RESET_PC,
    SETTLE_DEFAULT,
    TOHOST_BASE,
    TOHOST_FAIL,
    TOHOST_PASS,
    UART_DATA,
    UART_STATUS,
    unpack4,
)
from mvm_ref import mvm_int  # noqa: E402


def sext(val, bits):
    """bits 位补码 → Python int（可为负）。立即数、lb/lh 都用它。"""
    sign = 1 << (bits - 1)
    val &= (1 << bits) - 1
    return (val ^ sign) - sign


def get_bits(w, hi, lo):
    """含端点的位域，和 Verilog ir[hi:lo] 一样。"""
    return (w >> lo) & ((1 << (hi - lo + 1)) - 1)


class MvmModel:
    """与 rtl/mvm/mvm_copro.v 对齐的行为模型。

    class = 蓝图；iss.mvm = MvmModel() 做出实例。self.inp / self.wrow 就是寄存器。
    时间单位是「ISS 指令」而不是时钟：每执行一条指令 tick() 一次。
    延迟拍数仍用 settle+adc+1，固件是轮询 flag，不依赖绝对周期数。
    """
    def __init__(self):
        self.ctrl = 0
        self.status = 0
        self.config = SETTLE_DEFAULT | (ADC_DEFAULT << 8)
        self.inp = 0
        self.wrow = [0, 0, 0, 0]
        self.outpack = 0
        self.latency = 0
        self.busy_left = 0
        self.irq_en = 0
        self.irq = 0

    def _latency_cycles(self):
        settle = self.config & 0xFF
        adc = (self.config >> 8) & 0xFF
        return settle + adc + 1

    def start(self):
        """写 CTRL.START 时立刻算出 y（组合阵列），再进入 busy 倒计时。

        量化与 golden/mvm_ref.py 的 mvm_int 相同。mixed 向量会得到
        y=[33,22,16,25]，打包成 outpack=0x19101621=420484641
        （check_copro_fsm.py 终端 JSON 里那个十进制就是这个数）。
        """
        x = unpack4(self.inp)
        w = [unpack4(self.wrow[i]) for i in range(4)]
        y, _ = mvm_int(x, w)
        self.outpack = y[0] | (y[1] << 8) | (y[2] << 16) | (y[3] << 24)
        self.latency = self._latency_cycles()
        self.busy_left = self.latency
        self.status = MVM_ST_BUSY
        self.irq = 0

    def tick(self):
        """每条指令开头调用一次。busy_left 到 0 时拉 irq（若使能）。"""
        if self.busy_left > 0:
            self.busy_left -= 1
            if self.busy_left == 0:
                self.status = MVM_ST_DONE
                if self.irq_en:
                    self.irq = 1
                    self.status |= MVM_ST_IRQ

    def write(self, addr, data, wstrb):
        mask = 0
        for i in range(4):
            if wstrb & (1 << i):
                mask |= 0xFF << (8 * i)
        def merge(old):
            return (old & ~mask) | (data & mask)

        if addr == MVM_CTRL:
            self.ctrl = merge(self.ctrl)
            self.irq_en = 1 if (self.ctrl & MVM_CTRL_IRQ_EN) else 0
            if self.ctrl & MVM_CTRL_START:
                self.ctrl &= ~MVM_CTRL_START
                self.start()
                return "start"
        elif addr == MVM_IRQ:
            if data & 1:
                self.irq = 0
                self.status &= ~MVM_ST_IRQ
                return "irq_w1c"
        elif addr == MVM_CONFIG:
            self.config = merge(self.config)
        elif addr == MVM_INP:
            self.inp = merge(self.inp)
        elif addr in MVM_WROW:
            idx = MVM_WROW.index(addr)
            self.wrow[idx] = merge(self.wrow[idx])

    def read(self, addr):
        if addr == MVM_CTRL:
            return self.ctrl
        if addr == MVM_STATUS:
            return self.status
        if addr == MVM_IRQ:
            return 1 if self.irq else 0
        if addr == MVM_CONFIG:
            return self.config
        if addr == MVM_INP:
            return self.inp
        if addr in MVM_WROW:
            return self.wrow[MVM_WROW.index(addr)]
        if addr == MVM_OUTPACK:
            return self.outpack
        if addr == MVM_LATENCY:
            return self.latency
        return 0


class ISS:
    """RV32I 解释器 + MMIO。step() 顺序：tick 协处理器 → 采样中断 → 执行一条。

    hex_path: Path 是类型注解：提醒你传入的是路径对象，不是普通字符串。
    """

    def __init__(self, hex_path: Path):
        self.mem = bytearray(RAM_BYTES)          # 可变的字节数组，长度 8 KB，当 RAM 用
        # encoding="ascii"  关键字参数：按 ASCII 读文件
        # .split()  无参 = 按空白切开，得到 ["00000013", "00100093", ...] 这种 list
        words = hex_path.read_text(encoding="ascii").split()
        # enumerate(words)  同时给出下标和元素：i=0,1,2,...  w=那一行 hex 字符串
        # 相当于 C: for (i = 0; i < n; i++) { w = words[i]; ... }
        for i, w in enumerate(words):
            if 4 * i + 4 > RAM_BYTES:
                break
            val = int(w, 16)                    # 按十六进制把 "00000013" 读成整数
            # 切片 [a:b]  取下标 a 到 b-1 这一段，类似 C 的 memcpy(&mem[a], ..., b-a)
            # val.to_bytes(4, "little")  整数 → 4 字节，小端（低字节在低地址）
            self.mem[4 * i : 4 * i + 4] = val.to_bytes(4, "little")
        self.reg = [0] * 32                     # 32 个 0，当 x0..x31。* 对 list 是重复，不是乘法
        self.pc = RESET_PC
        self.mstatus = 0
        self.mie = 0
        self.mepc = 0
        self.mcause = 0
        self.mscratch = 0
        self.mtvec = 0x10
        self.mvm = MvmModel()
        self.tohost = 0
        self.uart_out = []
        self.cycles = 0
        self.instret = 0
        self.irq_seen = 0
        self.trace = []
        self.events = []
        self.irq_enter_pcs = []

    def set_reg(self, rd, val):
        # if rd:  rd=0 算假（x0 永远是 0，不能写）。相当于 C 的 if (rd != 0)
        if rd:
            self.reg[rd] = val & 0xFFFFFFFF

    def load(self, addr, size, unsigned=False):
        # unsigned=False 默认参数：不写第三个实参就当有符号扩展
        addr &= 0xFFFFFFFF
        if addr + size <= RAM_BYTES:
            # int.from_bytes(字节, "little")  小端字节 → 整数，to_bytes 的逆操作
            raw = int.from_bytes(self.mem[addr : addr + size], "little")
            if unsigned:
                return raw
            return sext(raw, 8 * size) & 0xFFFFFFFF
        word = self.mmio_read(addr & ~3)
        shift = 8 * (addr & 3)
        raw = (word >> shift) & ((1 << (8 * size)) - 1)
        if unsigned:
            return raw
        return sext(raw, 8 * size) & 0xFFFFFFFF

    def store(self, addr, size, val):
        addr &= 0xFFFFFFFF
        val &= (1 << (8 * size)) - 1
        if addr + size <= RAM_BYTES:
            self.mem[addr : addr + size] = val.to_bytes(size, "little")
            return
        aligned = addr & ~3
        shift = 8 * (addr & 3)
        wstrb = ((1 << size) - 1) << (addr & 3)
        data = (val << shift) & 0xFFFFFFFF
        self.mmio_write(aligned, data, wstrb)

    def mmio_read(self, addr):
        if addr == UART_DATA:
            return 0
        if addr == UART_STATUS:
            return 0
        if MVM_BASE <= addr < MVM_BASE + 0x100:
            return self.mvm.read(addr)
        if addr == TOHOST_BASE:
            return self.tohost
        return 0

    def mmio_write(self, addr, data, wstrb):
        if addr == UART_DATA and (wstrb & 1):
            ch = data & 0xFF
            self.uart_out.append(ch)
            # chr(65) → "A"。sys.stdout.write 写到标准输出，不自动换行（print 会换行）。
            # e2e_mvm.S 在三组向量都通过后会 putc('P','A','S','S','\n')，
            # 所以终端在 tohost=... 那一行之前会出现一个单独的 "PASS"。
            # smoke.S 不写 UART，所以冒烟仿真看不到 PASS，只有后面的计数行。
            sys.stdout.write(chr(ch))
            sys.stdout.flush()
            return
        if MVM_BASE <= addr < MVM_BASE + 0x100:
            ev = self.mvm.write(addr, data, wstrb)
            if ev:
                self.events.append({"cyc": self.cycles, "ev": ev, "addr": addr, "data": data})
            return
        if addr == TOHOST_BASE:
            self.tohost = data
            return

    def csr_read(self, csr):
        if csr == 0x300:
            return self.mstatus
        if csr == 0x304:
            return self.mie
        if csr == 0x305:
            return self.mtvec
        if csr == 0x340:
            return self.mscratch
        if csr == 0x341:
            return self.mepc
        if csr == 0x342:
            return self.mcause
        if csr == 0x344:
            mip = 0
            if self.mvm.irq:
                mip |= 1 << 11
            return mip
        return 0

    def csr_write(self, csr, val):
        val &= 0xFFFFFFFF
        if csr == 0x300:
            self.mstatus = val
        elif csr == 0x304:
            self.mie = val
        elif csr == 0x340:
            self.mscratch = val
        elif csr == 0x341:
            self.mepc = val
        elif csr == 0x342:
            self.mcause = val

    def take_irq(self):
        """指令边界：irq && MIE && MEIE 则跳 0x10，返回地址是尚未执行的 PC。

        每次真正进入这里：irq_seen += 1，cycles += 1（在 step 里），instret 不变。
        所以 e2e 终端的 irq_seen=3 就是三次 run_one 各进一次 handler；
        cycles - instret 也应当等于 3。
        """
        mie_global = (self.mstatus >> 3) & 1
        meie = (self.mie >> 11) & 1
        if self.mvm.irq and mie_global and meie:
            mpie = mie_global
            self.mepc = self.pc
            self.mcause = 11
            self.mstatus = (self.mstatus & ~(1 << 3)) | (mpie << 7)
            self.pc = self.mtvec
            self.irq_seen += 1
            self.irq_enter_pcs.append(self.mepc)
            self.events.append({"cyc": self.cycles, "ev": "irq_enter", "mepc": self.mepc})
            return True
        return False

    def step(self):
        # 先推进协处理器，再决定要不要进中断，最后才执行当前 PC 上的指令
        self.mvm.tick()
        if self.take_irq():
            self.cycles += 1
            return

        inst = self.load(self.pc, 4, unsigned=True)
        pc = self.pc
        nxt = (pc + 4) & 0xFFFFFFFF
        opcode = inst & 0x7F
        rd = get_bits(inst, 11, 7)
        rs1 = get_bits(inst, 19, 15)
        rs2 = get_bits(inst, 24, 20)
        f3 = get_bits(inst, 14, 12)
        f7 = get_bits(inst, 31, 25)
        iimm = sext(get_bits(inst, 31, 20), 12)
        simm = sext((get_bits(inst, 31, 25) << 5) | get_bits(inst, 11, 7), 12)
        bimm = sext(
            (get_bits(inst, 31, 31) << 12)
            | (get_bits(inst, 7, 7) << 11)
            | (get_bits(inst, 30, 25) << 5)
            | (get_bits(inst, 11, 8) << 1),
            13,
        )
        uimm = inst & 0xFFFFF000
        jimm = sext(
            (get_bits(inst, 31, 31) << 20)
            | (get_bits(inst, 19, 12) << 12)
            | (get_bits(inst, 20, 20) << 11)
            | (get_bits(inst, 30, 21) << 1),
            21,
        )
        r1 = self.reg[rs1]
        r2 = self.reg[rs2]

        def alu(op, a, b):
            a &= 0xFFFFFFFF
            b &= 0xFFFFFFFF
            if op == "add":
                return (a + b) & 0xFFFFFFFF
            if op == "sub":
                return (a - b) & 0xFFFFFFFF
            if op == "sll":
                return (a << (b & 31)) & 0xFFFFFFFF
            if op == "slt":
                return 1 if sext(a, 32) < sext(b, 32) else 0
            if op == "sltu":
                return 1 if a < b else 0
            if op == "xor":
                return a ^ b
            if op == "srl":
                return (a >> (b & 31)) & 0xFFFFFFFF
            if op == "sra":
                return sext(a, 32) >> (b & 31) & 0xFFFFFFFF
            if op == "or":
                return a | b
            if op == "and":
                return a & b
            return 0

        if opcode == 0x37:  # LUI
            self.set_reg(rd, uimm)
        elif opcode == 0x17:  # AUIPC
            self.set_reg(rd, (pc + uimm) & 0xFFFFFFFF)
        elif opcode == 0x6F:  # JAL
            self.set_reg(rd, nxt)
            nxt = (pc + jimm) & 0xFFFFFFFF
        elif opcode == 0x67:  # JALR
            self.set_reg(rd, nxt)
            nxt = ((r1 + iimm) & ~1) & 0xFFFFFFFF
        elif opcode == 0x63:
            take = False
            if f3 == 0:
                take = r1 == r2
            elif f3 == 1:
                take = r1 != r2
            elif f3 == 4:
                take = sext(r1, 32) < sext(r2, 32)
            elif f3 == 5:
                take = sext(r1, 32) >= sext(r2, 32)
            elif f3 == 6:
                take = r1 < r2
            elif f3 == 7:
                take = r1 >= r2
            if take:
                nxt = (pc + bimm) & 0xFFFFFFFF
        elif opcode == 0x03:
            addr = (r1 + iimm) & 0xFFFFFFFF
            if f3 == 0:
                self.set_reg(rd, self.load(addr, 1))
            elif f3 == 1:
                self.set_reg(rd, self.load(addr, 2))
            elif f3 == 2:
                self.set_reg(rd, self.load(addr, 4))
            elif f3 == 4:
                self.set_reg(rd, self.load(addr, 1, unsigned=True))
            elif f3 == 5:
                self.set_reg(rd, self.load(addr, 2, unsigned=True))
        elif opcode == 0x23:
            addr = (r1 + simm) & 0xFFFFFFFF
            if f3 == 0:
                self.store(addr, 1, r2)
            elif f3 == 1:
                self.store(addr, 2, r2)
            elif f3 == 2:
                self.store(addr, 4, r2)
        elif opcode == 0x13:
            shamt = r2 if False else (iimm & 31)
            if f3 == 0:
                self.set_reg(rd, alu("add", r1, iimm))
            elif f3 == 2:
                self.set_reg(rd, alu("slt", r1, iimm))
            elif f3 == 3:
                self.set_reg(rd, alu("sltu", r1, iimm & 0xFFFFFFFF))
            elif f3 == 4:
                self.set_reg(rd, alu("xor", r1, iimm))
            elif f3 == 6:
                self.set_reg(rd, alu("or", r1, iimm))
            elif f3 == 7:
                self.set_reg(rd, alu("and", r1, iimm))
            elif f3 == 1:
                self.set_reg(rd, alu("sll", r1, iimm))
            elif f3 == 5:
                if f7 & 0x20:
                    self.set_reg(rd, alu("sra", r1, shamt))
                else:
                    self.set_reg(rd, alu("srl", r1, shamt))
        elif opcode == 0x33:
            if f3 == 0 and f7 == 0:
                self.set_reg(rd, alu("add", r1, r2))
            elif f3 == 0 and f7 == 0x20:
                self.set_reg(rd, alu("sub", r1, r2))
            elif f3 == 1:
                self.set_reg(rd, alu("sll", r1, r2))
            elif f3 == 2:
                self.set_reg(rd, alu("slt", r1, r2))
            elif f3 == 3:
                self.set_reg(rd, alu("sltu", r1, r2))
            elif f3 == 4:
                self.set_reg(rd, alu("xor", r1, r2))
            elif f3 == 5 and f7 == 0:
                self.set_reg(rd, alu("srl", r1, r2))
            elif f3 == 5 and f7 == 0x20:
                self.set_reg(rd, alu("sra", r1, r2))
            elif f3 == 6:
                self.set_reg(rd, alu("or", r1, r2))
            elif f3 == 7:
                self.set_reg(rd, alu("and", r1, r2))
        elif opcode == 0x73:
            if f3 == 0:
                if iimm == 0:  # ecall
                    self.tohost = TOHOST_FAIL if self.tohost == 0 else self.tohost
                elif inst == 0x30200073:  # mret
                    mpie = (self.mstatus >> 7) & 1
                    self.mstatus = (self.mstatus & ~(1 << 3)) | (mpie << 3)
                    self.mstatus |= 1 << 7
                    nxt = self.mepc
                elif inst == 0x10500073:  # wfi
                    pass
            else:
                csr = get_bits(inst, 31, 20)
                old = self.csr_read(csr)
                src = rs1 if f3 in (1, 2, 3) else rs1  # zimm is rs1 field
                if f3 in (5, 6, 7):
                    src_val = rs1
                else:
                    src_val = r1
                new = old
                if f3 in (1, 5):
                    new = src_val
                elif f3 in (2, 6):
                    if rs1 != 0:
                        new = old | src_val
                elif f3 in (3, 7):
                    if rs1 != 0:
                        new = old & ~src_val
                self.set_reg(rd, old)
                if not (f3 in (2, 3, 6, 7) and rs1 == 0):
                    self.csr_write(csr, new)
        else:
            raise RuntimeError(f"illegal inst 0x{inst:08x} at pc=0x{pc:08x}")

        self.pc = nxt
        self.cycles += 1
        self.instret += 1

    def run(self, max_cycles=200000):
        # 停机条件：固件写了 TOHOST（非 0），或跑满 max_cycles。
        # smoke：第 3 条 sw 把 tohost 写成 1，循环结束，hang 不会被执行。
        # e2e ：三组 MVM + 软件黄金比对通过后 write_tohost(1) 才停。
        while self.cycles < max_cycles and self.tohost == 0:
            self.step()
        # "".join(...)  用空字符串当分隔符，把每个字符拼成一句。chr(c) 把字节变字符。
        uart = "".join(chr(c) for c in self.uart_out)
        return self.tohost, uart


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hex", type=Path)                 # 位置参数：hex 文件路径
    parser.add_argument("--max-cycles", type=int, default=200000)
    parser.add_argument("--report", type=Path)            # 没写就是 None，下面 if args.report 为假
    args = parser.parse_args()
    iss = ISS(args.hex)                                   # 构造 ISS 实例，hex 路径传给 __init__
    tohost, uart = iss.run(args.max_cycles)               # 位置参数：最大周期数
    # 空行：把前面 UART 吐出的 "PASS" 和下面的计数行分开。smoke 没有 UART，就多一个空行。
    print()
    # 终端（run_all 步骤 3）会出现下面两种之一：
    #
    #   smoke.hex:
    #     tohost=1 cycles=3 instret=3 irq_seen=0
    #       tohost=1  : smoke.S 的 sw t1, 0(t0) 写入 0x30000000，t1=1
    #       cycles=3  : lui / addi / sw 各 1 拍，写完 tohost 循环就停
    #       instret=3 : 三条都是普通指令，没有进中断
    #       irq_seen=0: 没碰 MVM
    #
    #   e2e_mvm.hex:
    #     tohost=1 cycles=5658 instret=5655 irq_seen=3
    #       tohost=1  : e2e_mvm.S 的 write_tohost(1)，成功码 TOHOST_PASS
    #       irq_seen=3: main 调 run_one 三次（zeros / fullscale / mixed），
    #                   每次 START 后 take_irq() 把 irq_seen += 1
    #       cycles - instret = irq_seen：take_irq() 占 1 拍但不执行指令，
    #                   所以 5658 - 5655 = 3。改固件后绝对周期会变，这个差应仍等于中断次数。
    print(f"tohost={tohost} cycles={iss.cycles} instret={iss.instret} irq_seen={iss.irq_seen}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        # 报告里不要写 Windows/Linux 绝对路径，否则换机器后不可复现
        try:
            hex_ref = str(args.hex.resolve().relative_to(ROOT))
        except ValueError:
            hex_ref = args.hex.name
        payload = {
            "hex": hex_ref,
            "tohost": tohost,
            "uart": uart,
            "cycles": iss.cycles,
            "instret": iss.instret,
            "irq_seen": iss.irq_seen,
            "irq_enter_pcs": iss.irq_enter_pcs,
            "events": iss.events,
            "mvm_latency_reg": iss.mvm.latency,
            "mvm_outpack": iss.mvm.outpack,
            "pass": tohost == TOHOST_PASS,
        }
        args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # 只在 e2e（run_all 传了 --report）出现：
        #   wrote D:\...\reports\iss_e2e.json
        print(f"wrote {args.report}")
    if tohost == TOHOST_PASS:
        # 终端最后一行：ISS_PASS。tohost==1 才算过（见 socmap.TOHOST_PASS）。
        # 固件失败会写 TOHOST=3，走到下面的 ISS_FAIL，run_all 随之非 0 退出。
        print("ISS_PASS")
        return 0
    print("ISS_FAIL")
    return 1


if __name__ == "__main__":
    # 直接 python iss.py foo.hex 时才跑；被 import 时只把 ISS 类借出去
    sys.exit(main())
