#!/usr/bin/env bash
# inner-admin 上的一键 VCS 串联脚本（登录节点内存不足时会被 Killed）。
# 推荐用 LSF：见 scripts/asic/run_vcs_unit.sh / run_vcs_soc.sh + bsub。
# 在仓库根目录执行；hex 先由 python scripts/sim/run_all.py 生成。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== unit MVM =="
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_mvm \
  -f tb/filelist.f \
  tb/unit/tb_mvm_copro.v
./simv_mvm

echo "== SoC e2e =="
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_e2e \
  -f tb/filelist.f \
  tb/soc/tb_soc_e2e.v
./simv_e2e

echo "== mixed real =="
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_mixed \
  rtl/mvm/mvm_array_digital.v \
  tb/mixed/mvm_array_real.sv \
  tb/mixed/tb_mixed_sv.sv
./simv_mixed
