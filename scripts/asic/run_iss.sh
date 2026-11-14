#!/bin/bash
# inner-admin 上一键跑 Python 闭环。就是远程调用 scripts/sim/run_all.py。
#
# [给你看的对照] 刚学 Python 的话：
#   这是 bash。PROJ=... 是写死的服务器路径；本机请直接 python scripts/sim/run_all.py
set -e
PROJ=/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
cd "$PROJ"
python3 scripts/sim/run_all.py
echo ISS_REMOTE_DONE
