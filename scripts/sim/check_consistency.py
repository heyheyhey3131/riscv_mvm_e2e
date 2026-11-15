#!/usr/bin/env python3
"""静态一致性检查：地址表 / 量化常量 / FSM 默认值不能各写各的。

检查对象：
  rtl/include/soc_cfg.vh      Verilog 宏（文档/校验基准）
  fw/include/mvm_hw.h         C 固件
  fw/python/socmap.py         Python（ISS / 汇编器 / 黄金模型）
  rtl/bus/simple_interconnect.v   RAM/UART/MVM/TOHOST 片选
  rtl/mvm/mvm_copro.v         OFF_* 偏移、cfg 复位值
  rtl/mvm/mvm_array_digital.v MVM_SCALE
  rtl/mem/sram_1rw.v          WORDS 默认值

这个脚本只做静态文本/常量检查，不替代 VCS 时序仿真。
"""

from __future__ import print_function

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fw" / "python"))

import socmap  # noqa: E402


def parse_verilog_defines(path):
    """解析 `define NAME value；只处理本工程用到的简单常量。"""
    env = {}
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^\s*`define\s+([A-Za-z_]\w*)\s+(.+?)\s*$", line)
        if not m:
            continue
        name = m.group(1)
        val = m.group(2).split("//")[0].strip()
        val = re.sub(
            r"32'[hH]([0-9A-Fa-f_]+)",
            lambda x: str(int(x.group(1).replace("_", ""), 16)),
            val,
        )
        val = re.sub(
            r"32'[dD]([0-9_]+)",
            lambda x: str(int(x.group(1).replace("_", ""), 10)),
            val,
        )
        val = val.replace("_", "")
        try:
            env[name] = eval(val, {"__builtins__": {}}, env)
        except Exception:
            # 不是简单常量就跳过，下面的关键项会单独报缺失
            pass
    return env


def parse_c_defines(path):
    """解析 #define；支持 (BASE + 0x04u)、(1u << 0) 这类表达式。"""
    env = {}
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^\s*#define\s+([A-Za-z_]\w*)\s+(.+?)\s*$", line)
        if not m:
            continue
        name = m.group(1)
        val = re.sub(r"/\*.*?\*/", "", m.group(2))
        val = val.split("//")[0].strip()
        val = re.sub(r"\b(0x[0-9A-Fa-f]+)[uUlL]\b", r"\1", val)
        val = re.sub(r"\b(\d+)[uUlL]\b", r"\1", val)

        def repl_ident(x):
            key = x.group(1)
            if key in env:
                return str(env[key])
            return key

        val = re.sub(r"\b([A-Za-z_]\w*)\b", repl_ident, val)
        try:
            env[name] = eval(val, {"__builtins__": {}}, env)
        except Exception:
            pass
    return env


def get_py(name):
    return getattr(socmap, name)


def main():
    vh = parse_verilog_defines(ROOT / "rtl" / "include" / "soc_cfg.vh")
    ch = parse_c_defines(ROOT / "fw" / "include" / "mvm_hw.h")

    errors = []

    def check(label, actual, expected):
        if actual is None:
            errors.append("%s: missing" % label)
        elif actual != expected:
            errors.append("%s: got %r, expected %r" % (label, actual, expected))

    # 1) Python 是唯一基准；C 与 Verilog 宏必须逐项相等
    pairs = [
        ("RAM_BASE", "RAM_BASE", "RAM_BASE"),
        ("RAM_BYTES", "RAM_BYTES", "RAM_BYTES"),
        ("RAM_WORDS", "RAM_WORDS", "RAM_WORDS"),
        ("RESET_PC", "RESET_PC", "RESET_PC"),
        ("STACK_TOP", "STACK_TOP", "STACK_TOP"),
        ("MTVEC", "MTVEC_RESET", "MTVEC_RESET"),
        ("UART_BASE", "UART_BASE", "UART_BASE"),
        ("UART_DATA", "UART_DATA", "UART_DATA"),
        ("UART_STATUS", "UART_STATUS", "UART_STATUS"),
        ("MVM_BASE", "MVM_BASE", "MVM_BASE"),
        ("MVM_CTRL", "MVM_CTRL", "MVM_CTRL"),
        ("MVM_STATUS", "MVM_STATUS", "MVM_STATUS"),
        ("MVM_IRQ", "MVM_IRQ", "MVM_IRQ"),
        ("MVM_CONFIG", "MVM_CONFIG", "MVM_CONFIG"),
        ("MVM_INP", "MVM_INP", "MVM_INP"),
        ("MVM_WROW0", "MVM_WROW0", "MVM_WROW0"),
        ("MVM_WROW1", "MVM_WROW1", "MVM_WROW1"),
        ("MVM_WROW2", "MVM_WROW2", "MVM_WROW2"),
        ("MVM_WROW3", "MVM_WROW3", "MVM_WROW3"),
        ("MVM_OUTPACK", "MVM_OUTPACK", "MVM_OUTPACK"),
        ("MVM_LATENCY", "MVM_LATENCY", "MVM_LATENCY"),
        ("TOHOST_BASE", "TOHOST_BASE", "TOHOST_BASE"),
        ("MVM_N", "MVM_N", "MVM_N"),
        ("MVM_BITS", "MVM_BITS", "MVM_BITS"),
        ("MVM_MAX", "MVM_MAX", "MVM_MAX"),
        ("MVM_SCALE", "MVM_SCALE", "MVM_SCALE"),
        ("SETTLE_DEFAULT", "MVM_SETTLE_DEFAULT", "MVM_SETTLE_DFLT"),
        ("ADC_DEFAULT", "MVM_ADC_DEFAULT", "MVM_ADC_DFLT"),
    ]
    for py_name, c_name, vh_name in pairs:
        expected = get_py(py_name)
        check("C " + c_name, ch.get(c_name), expected)
        check("VH " + vh_name, vh.get(vh_name), expected)

    # C 里额外有的控制/状态位
    c_extra = [
        ("MVM_CTRL_START", socmap.MVM_CTRL_START),
        ("MVM_CTRL_IRQ_EN", socmap.MVM_CTRL_IRQ_EN),
        ("MVM_ST_BUSY", socmap.MVM_ST_BUSY),
        ("MVM_ST_DONE", socmap.MVM_ST_DONE),
        ("MVM_ST_IRQ", socmap.MVM_ST_IRQ),
        ("TOHOST_PASS", socmap.TOHOST_PASS),
        ("TOHOST_FAIL", socmap.TOHOST_FAIL),
    ]
    for name, expected in c_extra:
        check("C " + name, ch.get(name), expected)

    # 2) mvm_copro 的 OFF_* 必须等于 Python 地址减 MVM_BASE
    copro_text = (ROOT / "rtl" / "mvm" / "mvm_copro.v").read_text(encoding="utf-8")
    offsets = {}
    for m in re.finditer(r"OFF_([A-Z0-9_]+)\s*=\s*8'h([0-9A-Fa-f]+)", copro_text):
        offsets["MVM_" + m.group(1)] = int(m.group(2), 16)
    for name in [
        "MVM_CTRL", "MVM_STATUS", "MVM_IRQ", "MVM_CONFIG", "MVM_INP",
        "MVM_WROW0", "MVM_WROW1", "MVM_WROW2", "MVM_WROW3",
        "MVM_OUTPACK", "MVM_LATENCY",
    ]:
        expected = get_py(name) - socmap.MVM_BASE
        check("RTL offset " + name, offsets.get(name), expected)

    # 3) 默认 cfg = {adc, settle}
    m = re.search(r"cfg\s*<=\s*32'h([0-9A-Fa-f_]+)", copro_text)
    reset_cfg = int(m.group(1).replace("_", ""), 16) if m else None
    expected_cfg = (socmap.ADC_DEFAULT << 8) | socmap.SETTLE_DEFAULT
    check("RTL reset cfg", reset_cfg, expected_cfg)

    # 4) 量化常量、RAM 容量
    arr_text = (ROOT / "rtl" / "mvm" / "mvm_array_digital.v").read_text(encoding="utf-8")
    m = re.search(r"localparam\s+integer\s+MVM_SCALE\s*=\s*(\d+)", arr_text)
    check("RTL mvm_array MVM_SCALE", int(m.group(1)) if m else None, socmap.MVM_SCALE)

    sram_text = (ROOT / "rtl" / "mem" / "sram_1rw.v").read_text(encoding="utf-8")
    m = re.search(r"parameter\s+integer\s+WORDS\s*=\s*(\d+)", sram_text)
    check("RTL sram WORDS", int(m.group(1)) if m else None, socmap.RAM_WORDS)

    bus_text = (ROOT / "rtl" / "bus" / "simple_interconnect.v").read_text(encoding="utf-8")
    m = re.search(r"localparam\s+\[31:0\]\s+RAM_BYTES\s*=\s*32'd(\d+)", bus_text)
    check("RTL bus RAM_BYTES", int(m.group(1)) if m else None, socmap.RAM_BYTES)

    if errors:
        print("CONSISTENCY_FAIL")
        for e in errors:
            print("  " + e)
        return 1

    print("CONSISTENCY_PASS  addresses/quantization/defaults agree across C, RTL, Python")
    return 0


if __name__ == "__main__":
    sys.exit(main())
