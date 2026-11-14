#!/usr/bin/env python3
"""周期精确的协处理器 FSM，对齐 rtl/mvm/mvm_copro.v。

本文件用一个 class 在 Python 里复刻 Verilog 状态机，不跑仿真器。
class ≈ Verilog 的 module：里面的 self.xxx 就是寄存器。

证明：
  latency = settle + adc + 1 = 13
  START 后第 13 拍 DONE=1 且 IRQ=1
  写 IRQ=1 后 irq 落下（W1C）
  寄存器读写回读正确
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fw" / "python"))
sys.path.insert(0, str(ROOT / "golden"))
from mvm_ref import mvm_int  # noqa: E402
from socmap import pack4, unpack4  # noqa: E402

# 一行赋四个值：左边四个名字，右边四个整数。
# 相当于 C: int ST_IDLE=0, ST_SETTLE=1, ST_ADC=2, ST_DONE=3;
ST_IDLE, ST_SETTLE, ST_ADC, ST_DONE = 0, 1, 2, 3


class CoproRtlFsm:
    """class = 一张蓝图。c = CoproRtlFsm() 做出一个实例，里面带着自己的寄存器。

    self 是「当前这个实例」。c.tick() 时，函数里的 self 就是 c。
    """

    def __init__(self):
        # __init__ 是构造函数：CoproRtlFsm() 时自动跑一遍，用来给寄存器赋初值
        self.ctrl = 0
        self.cfg = 0x00000408
        self.xin = 0
        self.wrow = [0, 0, 0, 0]
        self.outpack = 0
        self.latency = 0
        self.busy = 0
        self.done = 0
        self.irq = 0
        self.state = ST_IDLE
        self.cnt = 0

    @property
    def settle_n(self):
        # @property：调用时写 c.settle_n，不用写 c.settle_n()。读起来像变量，算起来像函数。
        v = self.cfg & 0xFF
        return v if v else 1

    @property
    def adc_n(self):
        v = (self.cfg >> 8) & 0xFF
        return v if v else 1

    def y_comb(self):
        x = unpack4(self.xin)                    # 位置参数 self.xin 传给 unpack4 的 word
        w = [unpack4(r) for r in self.wrow]      # 对每一行权重调用 unpack4
        y, _ = mvm_int(x, w)
        # *y 把列表拆开成多个位置参数：
        #   y = [10, 20, 30, 40]
        #   pack4(*y)  等价于  pack4(10, 20, 30, 40)
        # C 没有这种写法，只能 pack4(y[0], y[1], y[2], y[3])
        return pack4(*y)

    def write(self, off, data):
        start = off == 0x00 and (data & 1)
        if off == 0x00:
            self.ctrl = data & 2
        elif off == 0x08:
            if data & 1:
                self.irq = 0
        elif off == 0x0C:
            self.cfg = data
        elif off == 0x10:
            self.xin = data
        elif off == 0x20:
            self.wrow[0] = data
        elif off == 0x24:
            self.wrow[1] = data
        elif off == 0x28:
            self.wrow[2] = data
        elif off == 0x2C:
            self.wrow[3] = data
        return start

    def tick(self, start=False):
        # 与 RTL 同一拍：先写寄存器，再走 FSM（Verilog 同一 always 块）
        if self.state == ST_IDLE and start:
            self.busy = 1
            self.done = 0
            self.irq = 0
            self.cnt = self.settle_n
            # 终端 JSON 的 latency_reg / expected_latency_cycles。默认 8+4+1=13。
            self.latency = self.settle_n + self.adc_n + 1
            self.state = ST_SETTLE
        elif self.state == ST_SETTLE:
            if self.cnt == 1:
                self.cnt = self.adc_n
                self.state = ST_ADC
            else:
                self.cnt -= 1
        elif self.state == ST_ADC:
            if self.cnt == 1:
                self.outpack = self.y_comb()
                self.busy = 0
                self.done = 1
                self.irq = 1 if (self.ctrl & 2) else 0
                self.state = ST_DONE
            else:
                self.cnt -= 1
        elif self.state == ST_DONE:
            self.state = ST_IDLE


def run_one(xin, rows, irq_en=True):
    # irq_en=True 默认参数：不写第三个实参时当作 True
    # CoproRtlFsm()  空括号 = 调用构造函数，做出一个实例，赋给 c
    c = CoproRtlFsm()
    c.write(0x0C, 0x00000408)
    c.write(0x10, xin)
    c.write(0x20, rows[0])
    c.write(0x24, rows[1])
    c.write(0x28, rows[2])
    c.write(0x2C, rows[3])
    if irq_en:
        c.write(0x00, 2)
    start = c.write(0x00, 3 if irq_en else 1)
    irq_at = None
    done_at = None
    for t in range(1, 40):
        # start if t==1 else False  三元：第一拍把 start 传进去，之后都传 False
        # 相当于 C:  c.tick(t == 1 ? start : 0);
        c.tick(start if t == 1 else False)
        start = False
        if c.done and done_at is None:
            done_at = t
        if c.irq and irq_at is None:
            irq_at = t
    # W1C
    c.write(0x08, 1)
    irq_after_w1c = c.irq
    return {
        "latency_reg": c.latency,
        "done_at_cycle": done_at,
        "irq_at_cycle": irq_at,
        "outpack": c.outpack,
        "irq_after_w1c": irq_after_w1c,
        "done": c.done,
    }


def main():
    # 三组向量与 golden/mvm_ref.py 的 zeros / fullscale / mixed 相同。
    # mixed 的打包立即数：
    #   x      = {40,50,60,63}     → 0x3F3C3228
    #   wrow0  = {40,10,20,30}     → 0x1E140A28
    # run_one() 会 tick 到 DONE，并核对 latency/done/irq 都是第 13 拍。
    mixed = run_one(
        0x3F3C3228,
        [0x1E140A28, 0x1E141428, 0x1E141E28, 0x1E142828],
    )
    zeros = run_one(0, [0, 0, 0, 0])
    # [x] * 4  列表重复 4 遍，得到 [x, x, x, x]。不是算术乘法。
    full = run_one(0x3F3F3F3F, [0x3F3F3F3F] * 4)

    y_mixed, _ = mvm_int([40, 50, 60, 63], [
        [40, 10, 20, 30],
        [40, 20, 20, 30],
        [40, 30, 20, 30],
        [40, 40, 20, 30],
    ])
    exp_mixed = pack4(*y_mixed)

    errors = []
    for name, r, exp_y in (
        ("zeros", zeros, 0),
        ("fullscale", full, 0x3F3F3F3F),
        ("mixed", mixed, exp_mixed),
    ):
        if r["latency_reg"] != 13:
            errors.append(f"{name} latency {r['latency_reg']} != 13")
        if r["done_at_cycle"] != 13:
            errors.append(f"{name} done_at {r['done_at_cycle']} != 13")
        if r["irq_at_cycle"] != 13:
            errors.append(f"{name} irq_at {r['irq_at_cycle']} != 13")
        if r["outpack"] != exp_y:
            errors.append(f"{name} y {r['outpack']:08x} != {exp_y:08x}")
        if r["irq_after_w1c"] != 0:
            errors.append(f"{name} irq not cleared")

    out = {
        "expected_latency_cycles": 13,
        "expected_latency_ns_50mhz": 260,
        "zeros": zeros,
        "fullscale": full,
        "mixed": mixed,
        "errors": errors,
    }
    path = ROOT / "reports" / "copro_fsm.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    # {k: out[k] for k in (...)}  字典推导：只挑出这三个键做成新 dict 再打印
    # indent=2  关键字参数，JSON 每层缩进 2 空格
    #
    # 终端（run_all 步骤 4）会先打这一段 JSON，字段含义：
    #   expected_latency_cycles = 13     8(settle)+4(adc)+1，与 RTL 复位 cfg=0x0408 一致
    #   mixed.latency_reg       = 13     写进 LATENCY 寄存器的值，给面积/延迟报告用
    #   mixed.done_at_cycle     = 13     START 后第 13 拍 DONE 变 1
    #   mixed.irq_at_cycle      = 13     同一拍拉 irq（CTRL.IRQ_EN=1）
    #   mixed.outpack           = 420484641
    #       十进制看着吓人，其实是 pack(33,22,16,25) = 0x19101621
    #       33 | (22<<8) | (16<<16) | (25<<24) = 420484641
    #       与 mvm_ref.py 打印的 mixed y=[33,22,16,25] 相同
    #   mixed.irq_after_w1c     = 0      写 IRQ 寄存器 bit0=1 后 irq 落下（W1C）
    #   errors                  = []     空 = zeros/fullscale/mixed 全部核对通过
    print(json.dumps({k: out[k] for k in ("expected_latency_cycles", "mixed", "errors")}, indent=2))
    if errors:
        print("COPRO_FSM_FAIL")
        return 1
    # 13 cycle × 20 ns (50 MHz) = 260 ns，这就是题目要的「协处理器访问延迟」。
    # 不要和 ISS 的 cycles=5658 搞混：那是整段固件跑了多少指令拍。
    print("COPRO_FSM_PASS  latency=13 cycles @50MHz = 260 ns, W1C ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
