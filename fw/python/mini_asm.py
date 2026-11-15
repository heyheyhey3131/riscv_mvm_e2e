#!/usr/bin/env python3
"""极简 RV32I 汇编器。

本文件是一个模块：把 .S 文本变成 32-bit 机器码，再写成 $readmemh 用的 hex。
不依赖 RISC-V GCC，Windows / 虚拟机都能直接生成 imem.hex。

你会在这里看到的 Python 语法：
  class Assembler     一张蓝图；asm = Assembler() 做出实例
  def 方法(self, ...) 实例上的函数，self 就是那个实例
  字典 {键: 值}       查表：REGS["ra"] → 1
  字典推导            {f"x{i}": i for i in range(32)} 一次生成 x0..x31
  异常 class AsmError 出错时 raise，main 里 except 接住再 sys.exit(1)

支持：
  - RV32I 整数指令（无乘除、无压缩）
  - CSR：csrrw/csrrs/csrrc 以及 csrrwi/csrrsi/csrrci
  - mret / ecall / ebreak / wfi / nop
  - 伪指令：li（仅 12-bit 立即数）、mv、j、jal、ret、jr、call、beqz、bnez
  - 伪操作：.org .word .byte .equ .align .text
  - ABI 寄存器名与 x0..x31
  - 注释：# 或 //
"""

import argparse
import re                    # 正则：用规则从一行文本里抠出数字、寄存器名
import sys
from pathlib import Path

# 本文件在 <root>/fw/python/ → parents[2] = 仓库根
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fw" / "python"))
from socmap import MTVEC, STACK_TOP  # noqa: E402

# 字典推导：循环 32 次，键是 "x0".."x31"，值是 0..31
# 相当于 C:
#   for (i = 0; i < 32; i++) { 做键 "x0"+"i"；REGS[键] = i; }
# f"x{i}"  把 i 嵌进字符串：i=5 时得到 "x5"
REGS = {f"x{i}": i for i in range(32)}
# .update(另一个 dict)  把 ABI 别名合并进来：REGS["ra"] 也会等于 1
# 括号里那个 { "zero": 0, ... } 是传给 update 的位置参数（一个 dict）
REGS.update(
    {
        "zero": 0,
        "ra": 1,
        "sp": 2,
        "gp": 3,
        "tp": 4,
        "t0": 5,
        "t1": 6,
        "t2": 7,
        "s0": 8,
        "fp": 8,
        "s1": 9,
        "a0": 10,
        "a1": 11,
        "a2": 12,
        "a3": 13,
        "a4": 14,
        "a5": 15,
        "a6": 16,
        "a7": 17,
        "s2": 18,
        "s3": 19,
        "s4": 20,
        "s5": 21,
        "s6": 22,
        "s7": 23,
        "s8": 24,
        "s9": 25,
        "s10": 26,
        "s11": 27,
        "t3": 28,
        "t4": 29,
        "t5": 30,
        "t6": 31,
    }
)

CSRS = {
    "mstatus": 0x300,
    "mie": 0x304,
    "mtvec": 0x305,
    "mepc": 0x341,
    "mcause": 0x342,
    "mip": 0x344,
    "mscratch": 0x340,
}

# 值是元组 (opcode, funct3, funct7)。查表：opcode, f3, f7 = R_FUNCT["add"]
R_FUNCT = {
    "add": (0x33, 0, 0x00),
    "sub": (0x33, 0, 0x20),
    "sll": (0x33, 1, 0x00),
    "slt": (0x33, 2, 0x00),
    "sltu": (0x33, 3, 0x00),
    "xor": (0x33, 4, 0x00),
    "srl": (0x33, 5, 0x00),
    "sra": (0x33, 5, 0x20),
    "or": (0x33, 6, 0x00),
    "and": (0x33, 7, 0x00),
}

I_ALU = {
    "addi": (0x13, 0),
    "slti": (0x13, 2),
    "sltiu": (0x13, 3),
    "xori": (0x13, 4),
    "ori": (0x13, 6),
    "andi": (0x13, 7),
}

SHAMT_I = {
    "slli": (0x13, 1, 0x00),
    "srli": (0x13, 5, 0x00),
    "srai": (0x13, 5, 0x20),
}

LOADS = {"lb": (0x03, 0), "lh": (0x03, 1), "lw": (0x03, 2), "lbu": (0x03, 4), "lhu": (0x03, 5)}
STORES = {"sb": (0x23, 0), "sh": (0x23, 1), "sw": (0x23, 2)}
BRANCH = {
    "beq": (0x63, 0),
    "bne": (0x63, 1),
    "blt": (0x63, 4),
    "bge": (0x63, 5),
    "bltu": (0x63, 6),
    "bgeu": (0x63, 7),
}

CSR_I = {"csrrw": 1, "csrrs": 2, "csrrc": 3, "csrrwi": 5, "csrrsi": 6, "csrrci": 7}

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|-?0x[0-9A-Fa-f]+|-?\d+|[,()]")


class AsmError(Exception):
    """自定义异常：汇编出错时 raise AsmError("原因")。
    Exception 是 Python 自带的「出错」基类，继承它才能被 except 抓住。
    pass = 这个类本身没有额外代码，只当错误类型用。
    """
    pass


def parse_int(text: str) -> int:
    # 方法可以链式调用：先 lower() 变小写，再 replace("_", "") 去掉下划线。
    # replace 的两个位置参数：旧子串, 新子串。类似 C 的把 '_' 删掉。
    text = text.lower().replace("_", "")
    if text.startswith("0x"):
        # int(字符串, 进制)  第二个参数 16 = 按十六进制读。C 的 strtol(s, NULL, 16)
        return int(text, 16)
    return int(text, 10)


def signed_fits(value: int, bits: int) -> bool:
    return -(1 << (bits - 1)) <= value <= (1 << (bits - 1)) - 1


def ufit(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    return value & mask


def enc_r(rd, rs1, rs2, opcode, funct3, funct7):
    """R 型：add/sub/sll/... 以及 slli（shamt 放在 rs2 字段）。"""
    return (
        (ufit(funct7, 7) << 25)
        | (ufit(rs2, 5) << 20)
        | (ufit(rs1, 5) << 15)
        | (ufit(funct3, 3) << 12)
        | (ufit(rd, 5) << 7)
        | ufit(opcode, 7)
    )


def enc_i(rd, rs1, imm, opcode, funct3):
    """I 型：addi/load/jalr/CSR。imm 按无符号 12 位截断，调用方保证有符号范围。"""
    return (
        (ufit(imm, 12) << 20)
        | (ufit(rs1, 5) << 15)
        | (ufit(funct3, 3) << 12)
        | (ufit(rd, 5) << 7)
        | ufit(opcode, 7)
    )


def enc_s(rs1, rs2, imm, opcode, funct3):
    imm = ufit(imm, 12)
    return (
        ((imm >> 5) << 25)
        | (ufit(rs2, 5) << 20)
        | (ufit(rs1, 5) << 15)
        | (ufit(funct3, 3) << 12)
        | ((imm & 0x1F) << 7)
        | ufit(opcode, 7)
    )


def enc_b(rs1, rs2, imm, opcode, funct3):
    imm = ufit(imm, 13)
    return (
        ((imm >> 12) & 1) << 31
        | ((imm >> 5) & 0x3F) << 25
        | (ufit(rs2, 5) << 20)
        | (ufit(rs1, 5) << 15)
        | (ufit(funct3, 3) << 12)
        | ((imm >> 1) & 0xF) << 8
        | ((imm >> 11) & 1) << 7
        | ufit(opcode, 7)
    )


def enc_u(rd, imm, opcode):
    return (ufit(imm, 20) << 12) | (ufit(rd, 5) << 7) | ufit(opcode, 7)


def enc_j(rd, imm, opcode):
    imm = ufit(imm, 21)
    return (
        ((imm >> 20) & 1) << 31
        | ((imm >> 1) & 0x3FF) << 21
        | ((imm >> 11) & 1) << 20
        | ((imm >> 12) & 0xFF) << 12
        | (ufit(rd, 5) << 7)
        | ufit(opcode, 7)
    )


def tokenize(line: str):
    # split("#") 按 # 切开，得到 list；[0] 取第一部分 = 注释左边。
    # 再 split("//")[0] 同样去掉 // 注释。strip() 去掉首尾空白。
    line = line.split("#")[0].split("//")[0].strip()
    if not line:            # 空字符串算「假」，相当于 if (line[0] == '\0')
        return []           # 返回空 list
    # re.split(规则, 文本)  按空白或逗号切开。
    # [t for t in ... if t]  丢掉空串，留下真正的 token
    return [t for t in re.split(r"[\s,]+", line) if t]


def split_mem_operand(expr: str):
    """lw rd, off(rs)  -> (off, rs)"""
    m = re.match(r"(-?0x[0-9A-Fa-f]+|-?\d+)\(([A-Za-z0-9]+)\)", expr)
    if not m:
        raise AsmError(f"bad mem operand '{expr}'")
    return m.group(1), m.group(2)


class Assembler:
    """两遍扫描：pass1 收标签和地址，pass2 填立即数并编码。

    为什么两遍：beq 跳到后面的标签时，第一遍还不知道那个标签的地址。
    所以先扫一遍把所有 标签→地址 记进 self.labels，第二遍再编码。
    """

    def __init__(self):
        self.equ = {
            "STACK_TOP": STACK_TOP,
            "MTVEC": MTVEC,
        }
        self.labels = {}
        self.items = []  # (pc, kind, payload, lineno)
        self.pc = 0

    def resolve_reg(self, name: str) -> int:
        if name not in REGS:
            raise AsmError(f"unknown register {name}")
        return REGS[name]

    def resolve_csr(self, name: str) -> int:
        key = name.lower()
        if key in CSRS:
            return CSRS[key]
        return self.eval_imm(name)

    def eval_imm(self, text: str, pc=None) -> int:
        text = text.strip()
        if text in self.equ:
            return int(self.equ[text])
        if text in self.labels:
            return int(self.labels[text])
        try:
            return parse_int(text)
        except ValueError:
            raise AsmError(f"cannot evaluate '{text}'")

    def pass1(self, lines):
        """只处理标签、.equ、.org、.align、.word；指令占 4 字节往前推 PC。"""
        self.pc = 0
        self.labels = {}
        self.items = []
        for lineno, raw in enumerate(lines, 1):
            try:
                self._pass1_line(raw, lineno)
            except AsmError as e:
                raise AsmError(f"line {lineno}: {e}") from e

    def _pass1_line(self, raw, lineno):
        line = raw.split("#")[0].split("//")[0].strip()
        if not line:
            return
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
            if not m:
                break
            self.labels[m.group(1)] = self.pc
            line = m.group(2).strip()
            if not line:
                return
        toks = tokenize(line)
        if not toks:
            return
        op = toks[0].lower()
        if op == ".equ":
            self.equ[toks[1]] = self.eval_imm(toks[2])
            return
        if op == ".org":
            self.pc = self.eval_imm(toks[1])
            if self.pc & 1:
                raise AsmError(".org must be byte address")
            return
        if op == ".align":
            n = 1 << self.eval_imm(toks[1])
            while self.pc % n:
                self.items.append((self.pc, "word", 0, lineno))
                self.pc += 4
            return
        if op == ".word":
            for t in toks[1:]:
                self.items.append((self.pc, "word_expr", t, lineno))
                self.pc += 4
            return
        if op == ".text":
            return
        self.items.append((self.pc, "op", toks, lineno))
        self.pc += 4

    def expand(self, toks):
        op = toks[0].lower()
        a = toks[1:]
        if op == "nop":
            return ["addi", "x0", "x0", "0"]
        if op == "mv":
            return ["addi", a[0], a[1], "0"]
        if op == "not":
            return ["xori", a[0], a[1], "-1"]
        if op == "neg":
            return ["sub", a[0], "x0", a[1]]
        if op == "seqz":
            return ["sltiu", a[0], a[1], "1"]
        if op == "snez":
            return ["sltu", a[0], "x0", a[1]]
        if op == "j":
            return ["jal", "x0", a[0]]
        if op == "jal" and len(a) == 1:
            return ["jal", "ra", a[0]]
        if op == "jr":
            # jalr rd, rs1, imm：rd=x0，rs1=a[0]，imm=0
            return ["jalr", "x0", a[0], "0"]
        if op == "ret":
            return ["jalr", "x0", "0(ra)"]
        if op == "call":
            return ["jal", "ra", a[0]]
        if op == "beqz":
            return ["beq", a[0], "x0", a[1]]
        if op == "bnez":
            return ["bne", a[0], "x0", a[1]]
        if op == "li":
            return self._expand_li(a[0], a[1])
        if op == "la":
            return self._expand_li(a[0], a[1])
        return toks

    def _expand_li(self, rd, imm_tok):
        # 本教学汇编器按「一条源指令 = 一个字」处理，不能在这里变长成 lui+addi。
        # 因此 li 只接受 12-bit 有符号立即数；大常数请显式写 lui + addi。
        return ["addi", rd, "x0", imm_tok]

    def encode_op(self, pc, toks, lineno):
        """把一条（已展开伪指令的）助记符编成 32-bit。pc 用于算分支/jal 偏移。"""
        toks = self.expand(toks)
        op = toks[0].lower()
        a = toks[1:]

        def imm_of(text, bits=None, signed=True):
            val = self.eval_imm(text)
            if bits is not None:
                if signed and not signed_fits(val, bits):
                    raise AsmError(f"imm {val} does not fit in {bits}-bit signed")
                if not signed and not (0 <= val < (1 << bits)):
                    raise AsmError(f"imm {val} does not fit in {bits}-bit unsigned")
            return val

        if op in R_FUNCT:
            opcode, f3, f7 = R_FUNCT[op]
            rd, rs1, rs2 = self.resolve_reg(a[0]), self.resolve_reg(a[1]), self.resolve_reg(a[2])
            return enc_r(rd, rs1, rs2, opcode, f3, f7)

        if op in I_ALU:
            opcode, f3 = I_ALU[op]
            rd, rs1 = self.resolve_reg(a[0]), self.resolve_reg(a[1])
            return enc_i(rd, rs1, imm_of(a[2], 12, True), opcode, f3)

        if op in SHAMT_I:
            opcode, f3, f7 = SHAMT_I[op]
            rd, rs1 = self.resolve_reg(a[0]), self.resolve_reg(a[1])
            shamt = imm_of(a[2], 5, False)
            return enc_r(rd, rs1, shamt, opcode, f3, f7)

        if op in LOADS:
            opcode, f3 = LOADS[op]
            rd = self.resolve_reg(a[0])
            off, rs = split_mem_operand(a[1])
            return enc_i(rd, self.resolve_reg(rs), imm_of(off, 12), opcode, f3)

        if op in STORES:
            opcode, f3 = STORES[op]
            rs2 = self.resolve_reg(a[0])
            off, rs = split_mem_operand(a[1])
            return enc_s(self.resolve_reg(rs), rs2, imm_of(off, 12), opcode, f3)

        if op in BRANCH:
            opcode, f3 = BRANCH[op]
            rs1, rs2 = self.resolve_reg(a[0]), self.resolve_reg(a[1])
            target = self.eval_imm(a[2])
            off = target - pc
            if off & 1:
                raise AsmError("branch offset misaligned")
            if not signed_fits(off, 13):
                raise AsmError(f"branch offset {off} too far")
            return enc_b(rs1, rs2, off, opcode, f3)

        if op == "jal":
            rd = self.resolve_reg(a[0])
            target = self.eval_imm(a[1])
            off = target - pc
            if off & 1:
                raise AsmError("jal offset misaligned")
            if not signed_fits(off, 21):
                raise AsmError(f"jal offset {off} too far")
            return enc_j(rd, off, 0x6F)

        if op == "jalr":
            # jalr rd, off(rs)   or jalr rd, rs, off
            if len(a) == 2 and "(" in a[1]:
                rd = self.resolve_reg(a[0])
                off, rs = split_mem_operand(a[1])
                return enc_i(rd, self.resolve_reg(rs), imm_of(off, 12), 0x67, 0)
            rd, rs1 = self.resolve_reg(a[0]), self.resolve_reg(a[1])
            imm = imm_of(a[2], 12) if len(a) > 2 else 0
            return enc_i(rd, rs1, imm, 0x67, 0)

        if op == "lui":
            return enc_u(self.resolve_reg(a[0]), imm_of(a[1], 20, False), 0x37)
        if op == "auipc":
            return enc_u(self.resolve_reg(a[0]), imm_of(a[1], 20, False), 0x17)

        if op == "ecall":
            return enc_i(0, 0, 0, 0x73, 0)
        if op == "ebreak":
            return enc_i(0, 0, 1, 0x73, 0)
        if op == "mret":
            return 0x30200073
        if op == "wfi":
            return 0x10500073

        if op in CSR_I:
            f3 = CSR_I[op]
            rd = self.resolve_reg(a[0])
            csr = self.resolve_csr(a[1])
            if op.endswith("i"):
                rs1 = imm_of(a[2], 5, False)
            else:
                rs1 = self.resolve_reg(a[2])
            return enc_i(rd, rs1, csr, 0x73, f3)

        if op == "csrr":
            rd = self.resolve_reg(a[0])
            csr = self.resolve_csr(a[1])
            return enc_i(rd, 0, csr, 0x73, 2)  # csrrs rd, csr, x0
        if op == "csrw":
            csr = self.resolve_csr(a[0])
            rs1 = self.resolve_reg(a[1])
            return enc_i(0, rs1, csr, 0x73, 1)
        if op == "csrsi":
            csr = self.resolve_csr(a[0])
            imm = imm_of(a[1], 5, False)
            return enc_i(0, imm, csr, 0x73, 6)
        if op == "csrci":
            csr = self.resolve_csr(a[0])
            imm = imm_of(a[1], 5, False)
            return enc_i(0, imm, csr, 0x73, 7)

        raise AsmError(f"unknown opcode {op}")

    def pass2(self):
        """把 pass1 记下的指令编成 32-bit 字；分支/跳转立即数 = 目标 - 当前 PC。"""
        words = {}
        for pc, kind, payload, lineno in self.items:
            try:
                if kind == "word":
                    words[pc] = payload & 0xFFFFFFFF
                elif kind == "word_expr":
                    words[pc] = self.eval_imm(payload) & 0xFFFFFFFF
                else:
                    words[pc] = self.encode_op(pc, payload, lineno) & 0xFFFFFFFF
            except AsmError as e:
                raise AsmError(f"line {lineno}: {e}") from e
        return words

    def to_hex(self, words, size_bytes=8192):
        lines = []
        nwords = size_bytes // 4
        for i in range(nwords):
            addr = i * 4
            w = words.get(addr, 0)          # 这个地址没指令就填 0
            lines.append(f"{w:08x}")        # :08x = 8 位小写十六进制，不足补 0。类似 printf("%08x")
        # "\n".join(lines)  用换行把所有字拼成一大段文本，再 + "\n" 末尾多一个换行
        return "\n".join(lines) + "\n"


def _format_payload(kind, payload) -> str:
    if kind == "op":
        return " ".join(payload)
    if kind == "word":
        return f".word 0x{payload & 0xFFFFFFFF:08x}"
    if kind == "word_expr":
        return f".word {payload}"
    return repr(payload)


def format_pass1(asm: Assembler) -> str:
    """pass1 刚结束时的中间表示：标签已变成地址，指令还是助记符。"""
    lines = [
        "# pass1 结束：.S 已被切成「地址 + token」，还没有 32-bit 机器码。",
        "# .equ / labels 已经能查表；items 里的指令仍是文本。",
        "",
        "[.equ]",
    ]
    for name, val in asm.equ.items():
        lines.append(f"  {name} = 0x{int(val):x}")
    lines += ["", "[labels]"]
    for name, addr in sorted(asm.labels.items(), key=lambda kv: (kv[1], kv[0])):
        lines.append(f"  {addr:08x}  {name}")
    lines += ["", "[items]  # pc / 源文件行号 / 种类 / 仍是文本的指令"]
    for pc, kind, payload, lineno in asm.items:
        lines.append(
            f"  pc={pc:08x}  line={lineno:<4}  {kind:<10} {_format_payload(kind, payload)}"
        )
    return "\n".join(lines) + "\n"


def format_pass2(asm: Assembler, words) -> str:
    """pass2 刚结束时的中间表示：每条指令已经是 32-bit 机器字。"""
    lines = [
        "# pass2 结束：.S 已经变成 {地址: 32-bit 机器码}。",
        "# 后面 to_hex 不再编码，只是把这些字按 8KB RAM 铺成 hex 文本。",
        "",
        "[words]  # 地址  机器码    源文件行号  对应的 pass1 token",
    ]
    for pc, kind, payload, lineno in asm.items:
        w = words.get(pc, 0)
        lines.append(
            f"  {pc:08x}  {w:08x}  line={lineno:<4}  {_format_payload(kind, payload)}"
        )
    return "\n".join(lines) + "\n"


def assemble_file(src: Path, ram_bytes=8192, dump_prefix=None):
    """读一个 .S 文件 → (汇编器实例, {地址: 机器码})。

    dump_prefix 若给定（通常是将要写的 .hex 路径），则：
      pass1 一结束写  <stem>.pass1.txt
      pass2 一结束写  <stem>.pass2.txt
    用来对照「每一轮之后 .S 变成了什么」。
    """
    asm = Assembler()
    # Path.read_text 一次读进字符串；splitlines() 按行切成 list
    lines = src.read_text(encoding="utf-8").splitlines()
    asm.pass1(lines)
    if dump_prefix is not None:
        dump_prefix.with_suffix(".pass1.txt").write_text(format_pass1(asm), encoding="utf-8")
    words = asm.pass2()
    if dump_prefix is not None:
        dump_prefix.with_suffix(".pass2.txt").write_text(format_pass2(asm, words), encoding="utf-8")
    return asm, words


def main():
    parser = argparse.ArgumentParser(description="Mini RV32I assembler")
    parser.add_argument("src", type=Path)           # 位置参数：命令行第一个文件名
    parser.add_argument("-o", "--output", type=Path)  # 可选，没写就是 None
    parser.add_argument("--map", action="store_true")
    parser.add_argument(
        "--no-dump-ir",
        action="store_true",
        help="不写 pass1/pass2 中间文件（默认会写 <hex>.pass1.txt / .pass2.txt）",
    )
    args = parser.parse_args()
    out = args.output
    if out is None:
        out = args.src.with_suffix(".hex")          # 只换后缀：foo.S → foo.hex
        if args.src.parent.name == "asm":
            # stem = 不带后缀的文件名。字符串 + 拼接，得到 "e2e_mvm.hex"
            out = ROOT / "fw" / "hex" / (args.src.stem + ".hex")
    out.parent.mkdir(parents=True, exist_ok=True)
    dump_prefix = None if args.no_dump_ir else out
    asm, words = assemble_file(args.src, dump_prefix=dump_prefix)
    # asm.to_hex(words)  先调用方法得到整段 hex 文本，再作为 write_text 的位置参数
    out.write_text(asm.to_hex(words), encoding="ascii")
    # max(words)  对 dict 取 max 得到最大的键（这里是最大地址）
    # words 为空时 max 会报错，所以用  有内容 if words else 0
    used = max(words) if words else 0
    # 终端（run_all 步骤 2）：
    #   assembled .../smoke.S -> .../smoke.hex  (4 words, last=0xc)
    #   assembled .../e2e_mvm.S -> .../e2e_mvm.hex  (252 words, last=0x3ec)
    # len(words) = 真正编出机器码的字数（空洞 .org 不算）。
    # last = 最大地址：smoke 的 jal hang 在 0x0C；e2e 的 write_tohost 末字节到 0x3EC。
    print(f"assembled {args.src} -> {out}  ({len(words)} words, last=0x{used:x})")
    if dump_prefix is not None:
        print(f"  pass1 -> {out.with_suffix('.pass1.txt')}")
        print(f"  pass2 -> {out.with_suffix('.pass2.txt')}")
    if args.map:
        # asm.labels.items()  得到 (名字, 地址) 对的列表
        # sorted(..., key=lambda kv: kv[1])
        #   key= 关键字参数：用什么当排序依据
        #   lambda kv: kv[1]  匿名函数：输入一对 kv，返回 kv[1]（地址）
        #   所以按地址从小到大排，不是按名字
        #
        # run_all 只给 e2e_mvm.S 加了 --map。终端会打出：
        #     00000000  _start
        #     00000010  irq_handler
        #     00000048  main
        #     ...
        #     000003e4  write_tohost
        # :08x = 8 位小写十六进制。必须看到 _start=0x00、irq_handler=0x10，
        # 否则 CPU 复位 / 中断入口和固件对不上。
        for name, addr in sorted(asm.labels.items(), key=lambda kv: kv[1]):
            print(f"  {addr:08x}  {name}")


if __name__ == "__main__":
    try:
        main()
    except AsmError as e:
        # except 接住 raise 出来的错误；as e 把错误对象起名叫 e
        # file=sys.stderr 打印到「错误输出」，和普通 print 分开
        print(f"asm error: {e}", file=sys.stderr)
        sys.exit(1)
