#!/bin/sh
# inner-admin TSMC 28 HPC+ 数字库。只读 Techlib，工程写在 qjxiang/ic_proj 下。
#
# [给你看的对照] 刚学 Python 的话：
#   export NAME=value  把变量写进「环境」，之后 DC/VCS 都能读到。
#   相当于 Python 的 os.environ["TSMC28_ROOT"] = "..."，本机 ISS 用不到。
# 在 tcsh 里请用:  source scripts/asic/admin_tsmc28.env.sh   未必兼容；
# 推荐 bash -lc 'source scripts/asic/admin_tsmc28.env.sh && ...'

TSMC28_ROOT=/home/xxypro/xyxue/Techlib/TSMC28
STD_HOME=${TSMC28_ROOT}/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital

export TSMC28_ROOT STD_HOME

export TSMC28_LIBDIR=${STD_HOME}/Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a
export TSMC28_DB=tcbn28hpcplusbwp30p140tt0p9v25c.db
export TSMC28_LIB=${TSMC28_LIBDIR}/tcbn28hpcplusbwp30p140tt0p9v25c.lib
export TSMC28_LEF=${STD_HOME}/Back_End/lef/tcbn28hpcplusbwp30p140_110a/lef/tcbn28hpcplusbwp30p140.lef
export TSMC28_VERILOG_DIR=${STD_HOME}/Front_End/verilog/tcbn28hpcplusbwp30p140_110a

export PROJ_ROOT=/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
export WORK_T28=${PROJ_ROOT}/work_t28
