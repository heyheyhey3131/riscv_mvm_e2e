# t28 0.9 V，DUT = mvm_copro_top
#
# [给你看的对照] 刚学 Python 的话：
#   SDC 不是 Python，是给 DC/PT 的时序约束「购物清单」。
#   create_clock -period 20  = 告诉工具时钟是 50 MHz
#   set_clock_uncertainty 4  = 预留 20% 裕量（4/20），题目要求的接口裕量
# 工作点 50 MHz（20 ns）。题目要接口裕量 ≥ 20%：
#   把 4 ns 放进 uncertainty，PT 仍非负 WNS 即视为满足。
# 驱动单元按库有了再加 set_driving_cell（smoke 工程用 BUFFD2BWP12T40P140）。

create_clock -name core_clk -period 20.000 [get_ports clk]
set_clock_uncertainty 4.000 [get_clocks core_clk]

# 复位异步，不当同步路径签
set_false_path -from [get_ports rst_n]

# 总线口按 10% 周期做板级/宏间预算；clk/rst 除外
set_input_delay  2.000 -clock core_clk [remove_from_collection [all_inputs]  [get_ports {clk rst_n}]]
set_output_delay 2.000 -clock core_clk [all_outputs]
set_load 0.02 [all_outputs]
