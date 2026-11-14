#!/bin/bash
# SoC 端到端：必须在仓库根目录跑，$readmemh 才找得到 fw/hex/e2e_mvm.hex
#
# [给你看的对照] 刚学 Python 的话：
#   远端 VCS 跑整颗 SoC，对应本机的 iss.py + e2e_mvm.hex。路径写死在服务器上。
set -e
PROJ=/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
cd "$PROJ"
mkdir -p work_t28
vcs -full64 -sverilog -timescale=1ns/1ps \
  -o work_t28/simv_soc \
  -f tb/filelist.f \
  tb/soc/tb_soc_e2e.v
./work_t28/simv_soc
echo VCS_SOC_DONE
