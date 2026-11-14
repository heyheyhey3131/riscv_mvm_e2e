# 整 SoC 教学约束。真正报面积请用 mvm_copro_top.sdc。
#
# [给你看的对照] 刚学 Python 的话：
#   和 mvm_copro_top.sdc 同一套语法，只是 DUT 换成整颗 SoC。面积报告不要用这份。
# ser_tx / tohost 都是输出，按 2 ns output delay 签。

create_clock -name core_clk -period 20.000 [get_ports clk]
set_clock_uncertainty 4.000 [get_clocks core_clk]
set_false_path -from [get_ports rst_n]
set_output_delay 2.000 -clock core_clk [all_outputs]
set_load 0.02 [all_outputs]
