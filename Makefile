# 仓库根：Python 闭环。不需要 RISC-V GCC / Icarus。
#   make          黄金向量 + 汇编 + ISS（smoke 和 e2e）
#   make smoke    只冒烟
#   make iverilog ISS 后再调 Icarus（本机要有 iverilog）
#
# [给你看的对照] 刚学 Python 的话：
#   Makefile 不是 Python。你敲 make，make 程序按下面的规则调 python。
#   目标: 依赖          像函数：要做「iss」得先做完「asm」和「golden」
#   缩进的那一行        真正执行的命令，和 run_all.py 里 subprocess.run(...) 干的是同一件事
#   PYTHON ?= python    没指定就用 python；相当于默认参数

PYTHON ?= python

.PHONY: all golden asm iss smoke e2e iverilog

all: iss

golden:
	$(PYTHON) golden/mvm_ref.py

asm:
	$(PYTHON) fw/python/mini_asm.py fw/asm/smoke.S -o fw/hex/smoke.hex
	$(PYTHON) fw/python/mini_asm.py fw/asm/e2e_mvm.S -o fw/hex/e2e_mvm.hex --map

iss: asm golden
	$(PYTHON) scripts/sim/iss.py fw/hex/smoke.hex
	$(PYTHON) scripts/sim/iss.py fw/hex/e2e_mvm.hex --report reports/iss_e2e.json
	$(PYTHON) scripts/sim/check_copro_fsm.py
	$(PYTHON) scripts/sim/check_precision.py

smoke: asm
	$(PYTHON) scripts/sim/iss.py fw/hex/smoke.hex

e2e: asm
	$(PYTHON) scripts/sim/iss.py fw/hex/e2e_mvm.hex

iverilog:
	$(PYTHON) scripts/sim/run_all.py --iverilog
