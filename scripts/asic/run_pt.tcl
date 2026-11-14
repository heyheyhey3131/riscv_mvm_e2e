# PrimeTime：综合后 STA。WNS 在 uncertainty=4ns 下非负 => 50 MHz 有 20% 裕量。
#
# [给你看的对照] 刚学 Python 的话：
#   还是 Tcl。读 DC 产出的网表，按 SDC 算每条路径快没快过 20 ns。
#   不改电路，只「量时间」，像 Python 里读 json 再打印 max_err。

set PROJ_ROOT /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
set WORK ${PROJ_ROOT}/work_t28
set TSMC28_ROOT /home/xxypro/xyxue/Techlib/TSMC28
set STD_HOME ${TSMC28_ROOT}/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital
set LIBDIR ${STD_HOME}/Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a

set_app_var search_path [list $LIBDIR]
set_app_var link_library [list * tcbn28hpcplusbwp30p140tt0p9v25c.db]

read_verilog ${WORK}/results/mvm_copro_top.syn.v
link_design mvm_copro_top
source ${PROJ_ROOT}/constraints/mvm_copro_top.sdc

report_timing > ${WORK}/reports/pt_timing.rpt
report_constraint -all_violators > ${WORK}/reports/pt_violators.rpt
puts "PT_DONE"
exit
