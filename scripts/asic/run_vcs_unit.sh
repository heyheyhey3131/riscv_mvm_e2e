#!/bin/bash
# inner-admin：VCS 跑协处理器单元 TB（不需要 stdcell）
#
# [给你看的对照] 刚学 Python 的话：
#   服务器上的 iverilog 替代品。PROJ= 写死了远端路径，本机不用跑。
set -e
PROJ=/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
cd "$PROJ"
mkdir -p work_t28
cd work_t28
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o simv_mvm \
  ../rtl/mvm/mvm_array_digital.v \
  ../rtl/mvm/mvm_copro.v \
  ../rtl/top/mvm_copro_top.v \
  ../tb/unit/tb_mvm_copro.v
./simv_mvm
echo VCS_UNIT_DONE
