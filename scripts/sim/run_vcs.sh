#!/usr/bin/env bash
# EDA2035 上跑 VCS：单元 MVM、SoC e2e、混合 real 模型。
# 用法：ssh eda2035 后 cd 到本仓库（或 /ic_proj 副本）再执行。
# hex 要先在本机 python scripts/sim/run_all.py 生成并一起拷过去。
#
# [给你看的对照] 刚学 Python 的话：
#   本机没 VCS。这份脚本在 Linux 虚拟机里调商业仿真器，步骤和 run_iverilog.sh 同类。
#   dirname "$0"/../..  ≈  Path(__file__).resolve().parents[2]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_mvm \
  -f tb/filelist.f \
  tb/unit/tb_mvm_copro.v
./simv_mvm

vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_e2e \
  -f tb/filelist.f \
  tb/soc/tb_soc_e2e.v
./simv_e2e

# real 模型不进 filelist，避免被 DC 误综合
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_mixed \
  rtl/mvm/mvm_array_digital.v \
  tb/mixed/mvm_array_real.sv \
  tb/mixed/tb_mixed_sv.sv
./simv_mixed
