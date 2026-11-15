# 题目 G 完成情况报告

日期：2026-11-15（第三次：代码一致性审计 + 修复）  
工程：`riscv_mvm_e2e/`  
题目原文：`main_requirement.txt`

## 一句话结论

**功能闭环（RISC-V 写向量 → MVM → 中断读回 → 黄金比对）已经完成，并已在 inner-admin 复现。**  
**「全流程到版图」仍未完成：** VCS 编译解析通过后被系统 Killed；DC/PT/Innovus 没有成功产出面积、WNS、DEF/GDS。

不要把 ISS_PASS 说成已经签核或已经出 GDS。  
代码层面的问题与修复见 `reports/LOGIC_AUDIT.md`。

---

## 本次部署位置（按你的可写目录）

| 主机 | 路径 | 状态 |
|---|---|---|
| **inner-admin**（题目要求的 admin） | `/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e` | **主工程**，ISS 已在此跑通 |
| admin02 跳板 | `/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e` | 同源 tarball 备份（两机 **不是** 同一块盘） |
| 工艺库（只读，未改） | `/home/xxypro/xyxue/Techlib/TSMC28` | SVT `tcbn28hpcplusbwp30p140`，TT 0.9 V 25C |

标准单元库（综合脚本已写死这些路径）：

```
$TSMC28/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital/
  Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a/tcbn28hpcplusbwp30p140tt0p9v25c.db
  Back_End/lef/.../tcbn28hpcplusbwp30p140.lef
```

工作目录：`.../riscv_mvm_e2e/work_t28/`  
脚本：`scripts/asic/README_admin.md`、`run_dc.tcl`、`run_pt.tcl`、`run_vcs_unit.sh`、`run_iss.sh`

---

## 题目条款对照

| 条款 | 状态 | 证据 |
|---|---|---|
| RISC-V 核经总线挂协处理器 | **代码完成** | `rtl/core/rv32i_min.v` + `simple_interconnect.v` |
| 4×4 理想电流/电阻阵列 | **行为模型完成** | digital / real / Verilog-A |
| 6-bit ADC 行为模型 | **行为模型完成** | 量化 0..63；AMS 未跑 |
| 寄存器接口 | **完成** | `docs/memory_map.md` |
| 端到端写向量→MVM→读回比对 | **ISS 通过（本机 + inner-admin）** | UART `PASS`，`tohost=1`，5658 周期，irq×3 |
| 全流程到版图 | **未完成** | VCS 被 Killed；DC/PT/Innovus 未产出；无 GDS |
| t28 / 0.9 V | **库已对接，综合未出报告** | Techlib TSMC28 + `run_dc.tcl` |
| MVM 误差 ≤ 1 LSB | **通过（理想 / 1% 失配）** | inner-admin `PRECISION_PASS` |
| 总线读写正确 | ISS + FSM 通过；HDL 波形未拿到 | VCS 未跑完 |
| 中断握手正确 | **ISS 通过** | 三次 start→irq(+13)→W1C |
| PVT 接口裕量 ≥ 20% | 仅有 SDC | `uncertainty 4 ns @ 20 ns`；PT 未跑 |
| 协处理器面积 | **未测** | 等 `work_t28/reports/area.rpt` |
| 访问延迟 | **FSM/ISS 模型已测** | 13 cycle = 260 ns @ 50 MHz；无后仿值 |

---

## 本次（11-15）代码审计修复

已修复并加入回归：

- UART 忙时不再返回 ready，避免连续 `putc` 静默丢字符
- RAM 片选收紧到 8 KB；0x0000_2000 以上不再别名到 mem[0]
- `START` 只在 `wstrb[0]` 真正写 CTRL 字节 0 时触发
- C 固件补 `mie.MEIE` / `mstatus.MIE`，否则 `run_one` 永远等不到 flag
- `mini_asm` 修复 `jr` 伪指令；明确 `li` 只支持 12-bit
- 删除 `mvm_array_real` 未生效的 `MISMATCH` 参数
- ISS 报告不再写绝对路径
- 增加 `check_consistency.py` / `check_assembler.py`，`run_all.py` 自动跑
- 修正 README / asic README / area_latency 里过期的 EDA2035 描述

本地回归仍为：`ISS_PASS` ×2、`ASSEMBLER_PASS`、`CONSISTENCY_PASS`、`COPRO_FSM_PASS`、`PRECISION_PASS`。

## 本次（11-02 晚）实际跑通的命令

在 inner-admin：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
python3 scripts/sim/run_all.py
```

结果：`ISS_PASS` ×2、`COPRO_FSM_PASS`、`PRECISION_PASS`。

VCS 单元仿真：RTL **解析成功**（`tb_mvm_copro` 为 top），随后

```
run_vcs_unit.sh: line 13: 94601 Killed  vcs ...
```

典型是交互节点内存/队列把编译进程杀掉，不是 RTL 语法错。需要 `bsub` 或更大内存队列再跑。

DC：已 `nohup dc_shell -f scripts/asic/run_dc.tcl >& work_t28/dc_nohup.out &`  
看结果：

```tcsh
tail work_t28/dc_nohup.out
ls work_t28/reports
```

---

## 仍未完成（按对交差的杀伤力）

### P0 — 没有这些不能叫「全流程作业」

1. **VCS/Xcelium 把 `tb_mvm_copro` 和 `tb_soc_e2e` 跑出 PASS**（建议 LSF `bsub`，避免再被 Killed）
2. **DC 综合出 `area.rpt`**，填 `reports/area_latency.md`
3. **PT WNS**（uncertainty=4 ns 非负）证明 20% 裕量
4. **Innovus/ICC2 出 DEF/GDS**（需要 tech LEF；`N28_PRTF_Cad_v1d5a` 在同一 Techlib 下）

### P1 — 混合信号

- `tb/mixed` 未用 VCS 跑
- Verilog-A 未进 Virtuoso AMS
- 晶体管级 4×4 版图（题目允许理想阵列，可标选做）

### P2

- Verdi 波形：start / irq / mret / OUTPACK
- ss/ff corner（当前 NLDM 目录里 TT 0.9 V 25C 已确认；ss/ff 25C 文件名未扫到，需再列 `*.lib`）
- PicoRV32 替换教学核

---

后续怎么做：打开 **`docs/next_steps_tutorial.md`**（inner-admin 上按 A→G 站复制命令）。

## 哪些部分可以马上再推进

| 下一步 | 在哪做 | 怎么做 |
|---|---|---|
| 看 DC 是否已经写出面积 | inner-admin | `sed -n '1,80p' work_t28/dc_nohup.out`；有 `DC_DONE` 则拷 `work_t28/reports/area.rpt` |
| 用 LSF 重跑 VCS | inner-admin | `bsub -Is -n 4 bash scripts/asic/run_vcs_unit.sh`（队列名问组里） |
| SoC 端到端 HDL | inner-admin | 仿 `run_vcs_unit.sh` 加上 `tb/soc/tb_soc_e2e.v` 和 filelist |
| PT | inner-admin | DC 成功后 `pt_shell -f scripts/asic/run_pt.tcl` |
| Innovus | inner-admin | 补 tech LEF + `tcbn28hpcplusbwp30p140.lef`；先做 `mvm_copro_top` 不要上 8 KB RAM |
| AMS | inner-admin IC618 | `analog/*.va` + Spectre；非阻塞 |

Windows 本机：`python scripts/sim/run_all.py` 仍然是最快回归。

---

## 完成度（更新）

| 块 | 上次 | 现在 | 说明 |
|---|---|---|---|
| 架构 / 教程 | ~95% | ~95% | |
| 数字 RTL + 固件 | ~90% | ~90% | |
| 功能 / 精度 / 中断 | ~85% | **~90%** | inner-admin ISS 复现 |
| 混合信号 | ~40% | ~40% | |
| t28 综合 / STA / 版图 | ~10% | **~25%** | 库路径落地、脚本齐；DC 尚未成功，无面积无 GDS |
| 服务器部署 | 0 | **~80%** | 工程在 admin `ic_proj` 下，库只读引用 Techlib |
| **题目 G 整体** | ~45–50% | **约 55%** | 功能可演示；版图仍缺 |

---

## 和导师怎么说

> 数字功能已经在课题服务器 inner-admin 上复现：RISC-V 程序写 4×4 向量、中断读回、与黄金值比，误差在理想和 1% 失配下 ≤ 1 LSB，硬件延迟 13 周期（260 ns @ 50 MHz）。工程在 `/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e`，工艺指向 `/home/xxypro/xyxue/Techlib/TSMC28` 的 28HPC+ SVT 库。下一步是 DC 出面积、PT 签 20% 裕量、再用 LSF 把 VCS 跑完；模拟阵列目前是题目允许的行为模型。
