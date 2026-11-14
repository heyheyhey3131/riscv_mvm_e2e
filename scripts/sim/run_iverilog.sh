#!/usr/bin/env bash
# Icarus Verilog 三连：单元 MVM → smoke SoC → e2e SoC
# 在仓库根执行：bash scripts/sim/run_iverilog.sh
# 先跑 python scripts/sim/run_all.py 生成 fw/hex/*.hex
#
# [给你看的对照] 刚学 Python 的话：
#   这是 bash 脚本，不是 Python。run_all.py 在 Windows 上会改调 .ps1。
#   ROOT="$(cd "$(dirname "$0")/../.." && pwd)"  ≈  Path(__file__).resolve().parents[2]
#   set -euo pipefail  任何命令失败就停，≈ run() 里 if returncode != 0: sys.exit(...)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

IVERILOG="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"

# -g2012：TB 里用了 $fatal
FILES="rtl/core/rv32i_min.v rtl/bus/simple_interconnect.v rtl/mem/sram_1rw.v rtl/periph/uart_tx.v rtl/periph/tohost.v rtl/mvm/mvm_array_digital.v rtl/mvm/mvm_copro.v rtl/top/mvm_copro_top.v rtl/top/riscv_mvm_soc.v"

echo "== unit MVM =="
$IVERILOG -g2012 -o /tmp/tb_mvm.vvp -I rtl/include $FILES tb/unit/tb_mvm_copro.v
$VVP /tmp/tb_mvm.vvp

echo "== smoke SoC =="
$IVERILOG -g2012 -o /tmp/tb_smoke.vvp -I rtl/include $FILES tb/soc/tb_soc_smoke.v
$VVP /tmp/tb_smoke.vvp

echo "== e2e SoC =="
$IVERILOG -g2012 -o /tmp/tb_e2e.vvp -I rtl/include $FILES tb/soc/tb_soc_e2e.v
$VVP /tmp/tb_e2e.vvp

echo "IVERILOG_ALL_PASS"
