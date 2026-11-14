#!/usr/bin/env bash
# 可选：把 PicoRV32 拉到 third_party，供后续把 rv32i_min 换成工业核。
# 默认工程不包含该源码（约三千行），避免第一周被核本身淹没。
# 替换步骤见 third_party/README.md：总线 mem_* 不用改，IRQ 固件要改成 retirq。
#
# [给你看的对照] 刚学 Python 的话：
#   这不是 Python。git clone 把别人的 CPU 核下载下来。日常 ISS 闭环不需要跑它。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$ROOT/third_party/picorv32"
if [ -d "$DEST/.git" ]; then
  echo "already cloned: $DEST"
  exit 0
fi
git clone --depth 1 https://github.com/YosysHQ/picorv32.git "$DEST"
echo "cloned PicoRV32 (ISC license) -> $DEST"
echo "集成要点：cpu 端口换成 picorv32 的 mem_* ，ENABLE_IRQ=1，PROGADDR_RESET=0，PROGADDR_IRQ=0x10"
