# VCS:  vcs -f tb/filelist.f ...
# 路径相对仓库根。不含 testbench，由命令行再加 tb/xxx.v
# 顺序无强依赖；mvm_copro 例化 mvm_array_digital，综合工具会解析。
#
# [给你看的对照] 刚学 Python 的话：
#   这不是 Python。每一行是一个 .v 文件路径，给仿真器当「要编译哪些源文件」的清单。
#   类似 Python 里把模块路径放进 sys.path，只不过这里列的是 Verilog。
rtl/core/rv32i_min.v
rtl/bus/simple_interconnect.v
rtl/mem/sram_1rw.v
rtl/periph/uart_tx.v
rtl/periph/tohost.v
rtl/mvm/mvm_array_digital.v
rtl/mvm/mvm_copro.v
rtl/top/mvm_copro_top.v
rtl/top/riscv_mvm_soc.v
