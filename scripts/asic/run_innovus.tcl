# 教学级 Innovus：把 DC 网表布到 t28。不是签核版图。
#
# [给你看的对照] 刚学 Python 的话：
#   还是 Tcl。DC 给出门级网表之后，本脚本把标准单元摆到芯片上并连线。
#   日常 Python ISS 闭环到不了这一步。
# 启动（在 work_t28 目录）：
#   innovus -files ../scripts/asic/run_innovus.tcl -no_gui -log innovus.log
#
# 若 init_design 报 SITE / 电源名 / 层名，先停下来按教程第 5 站改三处：
#   SITE_NAME、init_pwr_net/init_gnd_net、TECH_LEF 金属栈。

set PROJ_ROOT /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
set TSMC28_ROOT /home/xxypro/xyxue/Techlib/TSMC28
set STD_HOME ${TSMC28_ROOT}/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital

set CELL_LEF ${STD_HOME}/Back_End/lef/tcbn28hpcplusbwp30p140_110a/lef/tcbn28hpcplusbwp30p140.lef
# 9LM 6X2R 是教学常用栈；和 stdcell LEF 对不上时换 FileList.txt 里其它 tlef
set TECH_LEF ${TSMC28_ROOT}/N28_PRTF_Cad_v1d5a/PR_tech/Cadence/LefHeader/HVH/tsmcn28_9lm6X2RRDL.tlef

set NETLIST ${PROJ_ROOT}/work_t28/results/mvm_copro_top.syn.v
set SDC     ${PROJ_ROOT}/work_t28/results/mvm_copro_top.syn.sdc

set SITE_NAME core
set PWR_NET   VDD
set GND_NET   VSS

setDesignMode -process 28

set init_verilog $NETLIST
set init_top_cell mvm_copro_top
set init_lef_file [list $TECH_LEF $CELL_LEF]
set init_mmmc_file ""
set init_pwr_net $PWR_NET
set init_gnd_net $GND_NET
init_design
source $SDC

floorPlan -site $SITE_NAME -r 1.0 0.65 5 5 5 5
globalNetConnect $PWR_NET -type pgpin -pin $PWR_NET -inst *
globalNetConnect $GND_NET -type pgpin -pin $GND_NET -inst *
addRing -nets [list $PWR_NET $GND_NET] -width 0.8 -spacing 0.8 -layer_top M9 -layer_bottom M9 -layer_left M8 -layer_right M8

placeDesign
ccopt_design
routeDesign

saveDesign ${PROJ_ROOT}/work_t28/results/mvm_copro_top.enc
defOut -floorplan -netlist -routing ${PROJ_ROOT}/work_t28/results/mvm_copro_top.def
saveNetlist ${PROJ_ROOT}/work_t28/results/mvm_copro_top.pnr.v
report_area  > ${PROJ_ROOT}/work_t28/reports/innovus_area.rpt
report_timing > ${PROJ_ROOT}/work_t28/reports/innovus_timing.rpt
puts "INNOVUS_DONE"
exit
