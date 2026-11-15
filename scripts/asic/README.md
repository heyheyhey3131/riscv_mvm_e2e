# 这个目录的脚本（inner-admin × TSMC28）

**不要把本文当成操作手册。** 现在的主路径是：

1. `docs/next_steps_tutorial.md`：A→G 站，DC / LSF+VCS / PT / Innovus 的命令与失败排查
2. `scripts/asic/README_admin.md`：库路径、环境与最短命令
3. `docs/mvm_layout_tutorial.md`：数字版图 + 模拟 4×4 阵列

文件职责：

| 文件 | 作用 |
|---|---|
| `run_dc.tcl` | DC 综合 `mvm_copro_top` |
| `run_pt.tcl` | 综合后 STA |
| `run_vcs_unit.sh` | 协处理器单元 TB |
| `run_vcs_soc.sh` | SoC 端到端 TB（必须在仓库根跑） |
| `run_vcs_mixed.sh` | SystemVerilog real 混合模型 |
| `run_innovus.tcl` | 教学级 APR（不是签核） |
| `admin_tsmc28.env.sh` | 库路径变量 |
| `project.conf` | 旧模板配置，保留作参考 |

DUT 仍然是 `mvm_copro_top`，不要综合带 8 KB RAM 的整颗 SoC。
