#!/usr/bin/env python3
"""mini_asm 回归：固定几条指令的机器码，防止改伪指令时悄悄破坏编码。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fw" / "python"))

from mini_asm import Assembler, AsmError  # noqa: E402


def assemble(text):
    asm = Assembler()
    asm.pass1(text.splitlines())
    return asm.pass2()


def main():
    text = "\n".join([
        "lui x5, 0x12345",
        "addi x6, x0, -1",
        "sw x6, 0(x5)",
        "ret",
        "jr x5",
        "mret",
    ])
    words = assemble(text)
    expected = {
        0x00: 0x123452B7,  # lui x5, 0x12345
        0x04: 0xFFF00313,  # addi x6, x0, -1
        0x08: 0x0062A023,  # sw x6, 0(x5)
        0x0C: 0x00008067,  # ret = jalr x0, 0(ra)
        0x10: 0x00028067,  # jr x5 = jalr x0, 0(x5)
        0x14: 0x30200073,  # mret
    }
    errors = []
    for pc, want in expected.items():
        got = words.get(pc)
        if got != want:
            errors.append("pc=0x%02x got=0x%08x want=0x%08x" % (pc, got or 0, want))

    # li 只支持 12-bit；2048 必须明确报错，而不是静默编成错误指令
    try:
        assemble("li x1, 2048")
        errors.append("li 2048 should raise AsmError")
    except AsmError:
        pass

    if errors:
        print("ASSEMBLER_FAIL")
        for e in errors:
            print("  " + e)
        return 1
    print("ASSEMBLER_PASS  lui/addi/sw/ret/jr/mret encodings and li range check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
