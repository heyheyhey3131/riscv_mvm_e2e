# Design Compiler：综合 mvm_copro_top，目标 t28 0.9 V tt25c
# 在 work_t28 目录启动： dc_shell -f ../scripts/asic/run_dc.tcl
#
# [给你看的对照] 刚学 Python 的话：
#   这是 Tcl，不是 Python。set NAME value  ≈  NAME = value
#   analyze / elaborate / compile  是 DC 的命令，把 Verilog 变成门级网表。

set PROJ_ROOT /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
set TSMC28_ROOT /home/xxypro/xyxue/Techlib/TSMC28
set STD_HOME ${TSMC28_ROOT}/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital
set LIBDIR ${STD_HOME}/Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a

set_app_var search_path [list $LIBDIR ${PROJ_ROOT}/rtl/mvm ${PROJ_ROOT}/rtl/top]
set_app_var target_library tcbn28hpcplusbwp30p140tt0p9v25c.db
set_app_var link_library [list * tcbn28hpcplusbwp30p140tt0p9v25c.db]
set_app_var synthetic_library {}

file mkdir reports
file mkdir results

analyze -format verilog [list \
    ${PROJ_ROOT}/rtl/mvm/mvm_array_digital.v \
    ${PROJ_ROOT}/rtl/mvm/mvm_copro.v \
    ${PROJ_ROOT}/rtl/top/mvm_copro_top.v \
]
elaborate mvm_copro_top
current_design mvm_copro_top
link
uniquify

source ${PROJ_ROOT}/constraints/mvm_copro_top.sdc

compile -map_effort medium

write -format verilog -hierarchy -output results/mvm_copro_top.syn.v
write_sdc results/mvm_copro_top.syn.sdc
report_area  > reports/area.rpt
report_timing > reports/timing.rpt
report_qor   > reports/qor.rpt
report_power > reports/power.rpt

puts "DC_DONE"
exit
