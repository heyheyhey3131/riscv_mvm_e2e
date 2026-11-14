# 课题服务器 inner-admin 上的 TSMC28 流程

工艺根：**只读** `/home/xxypro/xyxue/Techlib/TSMC28`  
工程根（可写）：`/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e`

标准单元（SVT BWP30P140，0.9 V tt 25C）：

```
.../T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital/
  Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a/tcbn28hpcplusbwp30p140tt0p9v25c.db
  Back_End/lef/.../tcbn28hpcplusbwp30p140.lef
```

inner-admin 登录环境已带 VCS / DC / PT / Innovus。tcsh 下请用 bash：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
bash scripts/asic/run_iss.sh
bash scripts/asic/run_vcs_unit.sh
mkdir -p work_t28
cd work_t28
dc_shell -f ../scripts/asic/run_dc.tcl
pt_shell -f ../scripts/asic/run_pt.tcl
```

**按站操作教程（推荐）：** `docs/next_steps_tutorial.md`

面积填 `reports/area_latency.md`。不要往 Techlib 里解压或改库。
