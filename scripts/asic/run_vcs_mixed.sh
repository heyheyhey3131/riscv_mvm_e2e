#!/bin/bash
# 远端 VCS 跑整数阵列 vs real 阵列，对应 check_precision.py / tb_mixed_sv.sv。
#
# [给你看的对照] 刚学 Python 的话：本机 ISS 闭环不需要这份脚本。
set -e
PROJ=/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
cd "$PROJ"
mkdir -p work_t28
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o work_t28/simv_mixed \
  rtl/mvm/mvm_array_digital.v \
  tb/mixed/mvm_array_real.sv \
  tb/mixed/tb_mixed_sv.sv
./work_t28/simv_mixed
echo VCS_MIXED_DONE
