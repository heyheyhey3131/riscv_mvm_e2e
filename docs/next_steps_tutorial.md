# 题目 G 后续推进教程（inner-admin × TSMC28）

面向已经跑通 ISS、工程已在课题服务器上的你。  
目标：把「功能闭环」推进到 **VCS 波形 + DC 面积 + PT 20% 裕量 + Innovus 版图**，然后把数字填进报告。

本教程默认你坐在 **inner-admin 的交互登录** 里（VNC 开终端，或 `telnet admin` 后看到 `admin:/home/xxypro/xyxue/Members/qjxiang>`）。  
登录壳是 **tcsh**。下面凡是 `bash ...` 或 `bsub ...` 的行，直接整行粘贴即可。

---

## 0. 先建立图像：还缺哪几块

已经有的：

```
RISC-V 写 x、W → START → 13 拍后 IRQ → 读 y → |y-gold|≤1 LSB → UART PASS
```

这是 Python ISS，在本机和 inner-admin 都过了。

题目还要的：

```
① HDL 仿真签字（VCS）
② DC 综合 → 面积
③ PT 时序 → uncertainty 4 ns 下 WNS≥0（=50 MHz 有 20% 裕量）
④ Innovus 布线 → DEF/面积（GDS 能出更好）
⑤ 把数字抄进 reports/area_latency.md
```

DUT **永远是** `mvm_copro_top`（协处理器），不要综合带 8 KB 行为 RAM 的 `riscv_mvm_soc`。SoC 只给仿真用。

建议顺序（不要跳）：

| 站 | 做什么 | 成功长什么样 | 大约耗时 |
|---|---|---|---|
| A | 确认工程和 license | `which dc_shell` 有路径，`echo $SNPSLMD_LICENSE_FILE` 非空 | 5 分钟 |
| B | 交互登录跑 DC | `work_t28/reports/area.rpt` 里有 Total cell area | 15–40 分钟 |
| C | LSF 跑 VCS 单元 TB | 日志出现 `TB_MVM_PASS` | 10–30 分钟 |
| D | VCS SoC 端到端 | `SOC_E2E_PASS`，irq≥3 | 20–40 分钟 |
| E | PT | `pt_timing.rpt` 里 slack ≥ 0 | 10 分钟 |
| F | Innovus | `mvm_copro_top.def` 存在 | 30–90 分钟 |
| G | 填报告 | `area_latency.md` 不再写「未测」 | 15 分钟 |

选做（H）：`tb/mixed`、Verilog-A AMS、模拟 4×4 版图（`docs/mvm_layout_tutorial.md`）。没有它们也能交差，简历上写「理想阵列 + ADC 行为模型」。

---

## 1. 环境规矩（违反就会重蹈覆辙）

### 1.1 两台机器不是同一块盘

| 主机 | 你的可写目录 | 用途 |
|---|---|---|
| inner-admin | `/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e` | **主工程，所有 EDA 在这里跑** |
| admin02 | 同路径的一份拷贝 | 备份；改文件不要只改 admin02 |

工艺库只读：

```
/home/xxypro/xyxue/Techlib/TSMC28
```

禁止：往 Techlib 解压、chmod、改 lef。综合脚本已经指向里面的 `.db` / `.lef`。

### 1.2 为什么上次 `nohup dc_shell` 日志是空的

`nohup` 从 telnet 助手拉起时 **不会 source 你的 `.cshrc`**，license 变量是空的，dc_shell 几乎立刻退出，什么都不写。

正确做法：

1. 自己登录 inner-admin（VNC 终端或手工 telnet）
2. 先检查 license
3. **前台**跑 `dc_shell -f ...`，或用 `bsub`（LSF 会带上登录环境）

```tcsh
echo $SNPSLMD_LICENSE_FILE
# 期望类似：5280@dellr910d
which dc_shell vcs pt_shell innovus
```

若 echo 为空：

```tcsh
source ~/.cshrc
echo $SNPSLMD_LICENSE_FILE
```

还空就不要往下走，先找组里管 license 的人。Cadence（Innovus）走的是 `$CDS_LIC_FILE`（登录环境里已有）。

### 1.3 为什么 VCS 显示 `Killed`

RTL **已经解析成功**（top = `tb_mvm_copro`），死在后面的编译。交互节点内存不够，内核直接杀进程，不是 Verilog 写错。

所以 VCS **不要**在登录节点前台硬扛，改走 LSF。队列（2026-11-02 实测）：

| 队列 | 当时状态 | 建议 |
|---|---|---|
| `interactive` | 空闲 | 优先：前台等结果 |
| `normal` | 有任务在跑，但仍 Open | 备选 |
| `admin` | 空闲 | 不要用，除非组里明确说可以 |

### 1.4 tcsh 坑

- 不要写 bash 的 `2>&1`，会报 `Ambiguous output redirect`
- 重定向两边：`cmd >& file`
- 后台：`cmd &`
- 本教程尽量用 `bash scripts/asic/xxx.sh`，把重定向藏进 bash

---

## 2. 第 A 站：确认工程还在（2 分钟）

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
ls rtl/mvm scripts/asic fw/hex
python3 scripts/sim/run_all.py
```

必须再看到：`ISS_PASS`、`ASSEMBLER_PASS`、`CONSISTENCY_PASS`、`COPRO_FSM_PASS`、`PRECISION_PASS`。  
这一步不过，后面的波形和版图没有意义。

标准单元（脚本已写死，你只需知道在哪）：

```
.../T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital/
  Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a/tcbn28hpcplusbwp30p140tt0p9v25c.db
  Back_End/lef/tcbn28hpcplusbwp30p140_110a/lef/tcbn28hpcplusbwp30p140.lef
```

确认库文件在：

```tcsh
ls /home/xxypro/xyxue/Techlib/TSMC28/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital/Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_180a/tcbn28hpcplusbwp30p140tt0p9v25c.db
```

---

## 3. 第 B 站：DC 综合（出面积，最优先）

题目要「协处理器面积」。没有 `area.rpt` 就填不了报告。

### 3.1 前台跑（推荐第一次）

登录环境确认 license 之后：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
mkdir -p work_t28
cd work_t28
dc_shell -f ../scripts/asic/run_dc.tcl
```

脚本会：

1. 读三个 Verilog：`mvm_array_digital.v`、`mvm_copro.v`、`mvm_copro_top.v`
2. 链 TT 0.9 V 25C 的 `.db`
3. 读 `constraints/mvm_copro_top.sdc`（20 ns 时钟 + **4 ns uncertainty**）
4. `compile -map_effort medium`
5. 写出网表和报告

成功时终端最后有 `DC_DONE`，并且：

```
work_t28/results/mvm_copro_top.syn.v
work_t28/results/mvm_copro_top.syn.sdc
work_t28/reports/area.rpt
work_t28/reports/timing.rpt
```

### 3.2 看面积（抄报告用）

```tcsh
grep -n "Number of ports\|Combinational area\|Noncombinational area\|Total cell area\|Total area" reports/area.rpt
```

把 **Total cell area** 抄到 `reports/area_latency.md`。单位是库的 area unit（通常 μm² 量级的 cell area，不是芯片 mm²）。版图面积等 Innovus 再填。

### 3.3 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 立刻退出、几乎无日志 | 没 license | 回到 1.2，不要 nohup |
| `Unable to find ...tt0p9v25c.db` | search_path 或文件不存在 | 跑第 A 站的 `ls ...db` |
| `Error: Can't resolve reference` | 少读了一个 .v | 三个文件都要在 analyze 列表里 |
| `No clock` / 全 unconstrained | 没 source 到 sdc | 确认 `mvm_copro_top.sdc` 的端口名是 `clk` / `rst_n` |
| `compile` 很慢或被 Killed | 登录节点内存 | 改用下面的 bsub |

### 3.4 改用 LSF（登录节点又被杀时）

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
mkdir -p work_t28
bsub -q interactive -I -n 4 -R "rusage[mem=8000]" \
  "cd work_t28 && dc_shell -f ../scripts/asic/run_dc.tcl"
```

`-I`：前台等，输出打在当前终端。  
`interactive` 若不允许你投：

```tcsh
bsub -q normal -n 4 -R "rusage[mem=8000]" \
  -o work_t28/bsub_dc.log \
  "cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/work_t28 && dc_shell -f ../scripts/asic/run_dc.tcl"
bjobs
```

看日志：

```tcsh
tail work_t28/bsub_dc.log
```

搜 `DC_DONE`。

---

## 4. 第 C 站：VCS 单元仿真（HDL 签字）

证明协处理器寄存器、13 拍延迟、IRQ、误差 ≤ 1 LSB，**不经过 CPU**。

### 4.1 用 LSF 跑（不要再在登录节点直接 vcs）

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
mkdir -p work_t28
bsub -q interactive -I -n 4 -R "rusage[mem=8000]" \
  bash scripts/asic/run_vcs_unit.sh
```

成功标志（日志末尾）：

```
TB_MVM_PASS
VCS_UNIT_DONE
```

仿真会打三组向量：zeros / fullscale / mixed，并检查 `latency==13`、`irq` 次数。

### 4.2 若 `interactive` 投不进去

```tcsh
bsub -q normal -n 4 -R "rusage[mem=8000]" \
  -o work_t28/bsub_vcs_unit.log \
  bash /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/scripts/asic/run_vcs_unit.sh
bjobs
# 结束后：
grep TB_MVM_PASS work_t28/bsub_vcs_unit.log
```

### 4.3 看波形（交差截图）

仿真通过后，用 Verdi 打开（工作目录在 `work_t28` 时）：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/work_t28
# 若脚本没加 -debug_access：先在 run_vcs_unit.sh 的 vcs 行加上
#   -debug_access+all -kdb
# 再重编一次，然后：
verdi -ssf novas.fsdb &
```

第一次可以先改脚本再投 LSF。要截的信号：

- `tb_mvm_copro.clk`
- `valid` / `ready` / `addr` / `wdata` / `wstrb`
- `dut.u_mvm.state`（IDLE→SETTLE→ADC→DONE）
- `irq`
- `rdata`（读 OUTPACK 那一拍）

截一张：**写 START → 13 个时钟后 irq 拉高 → 写 IRQ=1 后 irq 落下**。

没有 fsdb 时，VCS 加 `+vcdpluson` 或在 TB 里 `$dumpfile/$dumpvars` 也行，能交差即可。

---

## 5. 第 D 站：VCS SoC 端到端

证明 RISC-V 固件在 **真 RTL** 上也能 PASS，不只是 Python ISS。

**必须在仓库根跑**（`$readmemh("fw/hex/e2e_mvm.hex")` 相对当前目录）：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
bsub -q interactive -I -n 4 -R "rusage[mem=16000]" \
  bash scripts/asic/run_vcs_soc.sh
```

成功：

```
SOC_E2E_PASS
```

终端里应出现 `PASS`（UART），`tohost=1`，`irq_count>=3`。

失败对照：

| 现象 | 先查 |
|---|---|
| `$readmemh` 打不开 hex | 是不是在 `work_t28` 里跑的？改回仓库根 |
| `TIMEOUT pc=...` | 中断没进 `0x10`：看 `dut.u_cpu.pc`、`dut.irq_mvm` |
| `SOC_E2E_FAIL` tohost=3 | 固件黄金比对失败：先确认单元 TB 已 PASS |
| 又是 `Killed` | 把 mem 加到 16000，或换 `normal` 队列 |

波形再截一张：`pc` 在 `0x10`（handler）→ `mret` 回来 → 写 TOHOST=1。

---

## 6. 第 E 站：PrimeTime（20% 裕量）

前置：第 B 站的 `mvm_copro_top.syn.v` 已存在。

SDC 已经把 20% 写成 **4 ns uncertainty**（周期 20 ns）。PT 在这个约束下 WNS ≥ 0，就可以在报告里写「TT 0.9 V 25C 满足 ≥20% 接口裕量」。

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/work_t28
pt_shell -f ../scripts/asic/run_pt.tcl
```

或：

```tcsh
bsub -q interactive -I \
  "cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/work_t28 && pt_shell -f ../scripts/asic/run_pt.tcl"
```

成功有 `PT_DONE` 和 `work_t28/reports/pt_timing.rpt`。

看 slack：

```tcsh
grep -i "slack" reports/pt_timing.rpt | head
grep -i "VIOLATED\|MET" reports/pt_timing.rpt | head
```

- **MET 且 slack ≥ 0**：抄 WNS 进 `area_latency.md`，20% 这一条算过（TT）
- **VIOLATED**：先不要改题目指标。把 `compile` 换成 `compile_ultra`，或把时钟放到 25 ns 做对照实验，再考虑减 uncertainty 是否诚实（不建议为交差把 4 ns 改小）

ss/ff：当前 NLDM 目录已确认有 `tt0p9v25c`。其它 corner 文件名若没有 `ssg0p9v25c`，报告里写清「只签 TT；ss/ff 库文件未在该目录找到」，比假装 PVT 齐全更好。

---

## 7. 第 F 站：Innovus 教学版图

前置：DC 网表 + syn.sdc。

教学脚本：`scripts/asic/run_innovus.tcl`  
它会 floorplan → 电源环 → place → CTS → route → 导出 DEF。  
**不是** foundry 签核；目的是「全流程到版图」四个字有东西可交。

MVM **模拟阵列**怎么画、和数字宏怎么拼、资料列表：见 **`docs/mvm_layout_tutorial.md`**（本文只负责 Innovus 命令）。

### 7.1 先核对 SITE 和电源名（5 分钟，别跳）

```tcsh
grep SITE /home/xxypro/xyxue/Techlib/TSMC28/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital/Back_End/lef/tcbn28hpcplusbwp30p140_110a/lef/tcbn28hpcplusbwp30p140.lef | head
grep "PIN V" /home/xxypro/xyxue/Techlib/TSMC28/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/TSMCHOME/digital/Back_End/lef/tcbn28hpcplusbwp30p140_110a/lef/tcbn28hpcplusbwp30p140.lef | head
```

把看到的 SITE 名字、电源脚名字，对照脚本顶部的：

```
set SITE_NAME core
set PWR_NET   VDD
set GND_NET   VSS
```

不一致就改 tcl 再跑。金属栈默认：

```
.../N28_PRTF_Cad_v1d5a/PR_tech/Cadence/LefHeader/HVH/tsmcn28_9lm6X2RRDL.tlef
```

`init_design` 若抱怨 layer，到 `FileList.txt` 换一个 tlef（同目录还有 7lm/8lm/10lm）。

### 7.2 跑

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/work_t28
bsub -q interactive -I -n 4 -R "rusage[mem=16000]" \
  innovus -files ../scripts/asic/run_innovus.tcl -no_gui -log innovus.log
```

成功日志有 `INNOVUS_DONE`，产物：

```
work_t28/results/mvm_copro_top.enc
work_t28/results/mvm_copro_top.def
work_t28/results/mvm_copro_top.pnr.v
work_t28/reports/innovus_area.rpt
```

版图面积从 `innovus_area.rpt` 或 Innovus 里 `floorPlan` 的 core/die 尺寸抄。截一张 floorplan/route 顶视图即可。

GDS：没有 layer map 时不要硬 streamOut。DEF + 截图对教学作业足够。组里若有 `gds2.map`，再补 `streamOut`。

---

## 8. 第 G 站：填报告（交差文本）

打开仓库里的 `reports/area_latency.md`，按下面填，不要把 ISS 的 5658 指令当成硬件延迟。

| 栏 | 从哪抄 |
|---|---|
| Combinational / Sequential / Total cell area | `work_t28/reports/area.rpt` |
| 版图面积 μm² | Innovus `innovus_area.rpt` 或 die size |
| MVM_LATENCY | 已填：**13 cycle / 260 ns** |
| TT WNS | `work_t28/reports/pt_timing.rpt` |
| 20% 裕量 | WNS≥0 则写「满足（uncertainty=4 ns @ 20 ns）」 |
| 工艺 | TSMC 28HPC+ SVT BWP30P140，0.9 V tt 25C |
| 库路径 | `/home/xxypro/xyxue/Techlib/TSMC28/...` |

`reports/G_COMPLETION_STATUS.md` 把「面积未测 / 版图未开始」改成实际状态。

答辩可以这样说（不要说已经流片）：

> 协处理器在 TSMC 28HPC+ 0.9 V TT 下综合，面积 xxx μm²，50 MHz 约束含 20% uncertainty，PT WNS 为 xxx ns。访问延迟由 FSM 和仿真共同确认为 13 周期。功能上 RISC-V 端到端 PASS，误差 ≤ 1 LSB。模拟阵列是理想行为模型。

---

## 9. 选做 H：混合信号

### 9.1 SystemVerilog real（不需要 Spectre）

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
bsub -q interactive -I bash scripts/asic/run_vcs_mixed.sh
```

期望 `MIXED_SV_PASS`。证明电流求和量化后与整数黄金差 ≤ 1 LSB。

### 9.2 Verilog-A + Virtuoso

1. IC618 打开自己的库（建在 `qjxiang` 下，不要写进 Techlib）
2. 按 `analog/README.md` 把 `dac6.va`、`mvm_array_4x4.va`、`adc6.va` 建成 Verilog-A cell
3. 数字块用 `mvm_copro` 的 RTL 或 DC 网表
4. AMS 跑一组 mixed 向量，导出码与 `golden/vectors.json` 比

这一步加分，不是 P0。

---

## 10. 故障速查

| 你看到的 | 含义 | 下一步 |
|---|---|---|
| `ISS_PASS` 但 VCS 没跑 | 功能有了，HDL 没签字 | 第 C 站，必须 bsub |
| `Killed` 在 vcs 编译 | 登录节点内存 | `-R "rusage[mem=8000]"` + 队列 |
| dc_shell 秒退、日志 0 字节 | license 环境没带上 | 交互登录；禁止裸 nohup |
| `Ambiguous output redirect` | tcsh 收到了 `2>&1` | 改用 `>& file` 或包进 bash |
| `Unable to resolve VDD` | 电源脚不叫 VDD | grep LEF PIN，改 innovus tcl |
| `Cannot find site core` | SITE 名不对 | grep SITE，改 `SITE_NAME` |
| PT VIOLATED | 4 ns 裕量吃紧 | compile_ultra；仍失败就如实写 WNS |
| 两台机器文件不一致 | admin02 ≠ inner-admin 磁盘 | 只在 inner-admin 上改、只在那边跑 |

---

## 11. 完成判据（自己勾）

数字全流程可以交差，当且仅当下面都有：

- [ ] inner-admin 上 `python3 scripts/sim/run_all.py` 仍 PASS
- [ ] `TB_MVM_PASS`（VCS 单元）
- [ ] `SOC_E2E_PASS`（VCS SoC）
- [ ] `work_t28/reports/area.rpt` 有 Total cell area
- [ ] `work_t28/reports/pt_timing.rpt` 的 WNS 已抄进 `area_latency.md`
- [ ] `work_t28/results/mvm_copro_top.def`（或 Innovus 截图）
- [ ] 一张 IRQ 握手波形截图

全部勾完，题目 G 的数字部分可以从「约 55%」收到「可答辩」。模拟晶体管版图仍然是加分项。

---

## 12. 命令备忘（按顺序复制）

```tcsh
# A 确认
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
source ~/.cshrc
echo $SNPSLMD_LICENSE_FILE
python3 scripts/sim/run_all.py

# B DC
mkdir -p work_t28
cd work_t28
dc_shell -f ../scripts/asic/run_dc.tcl
grep "Total cell area" reports/area.rpt

# C VCS 单元
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e
bsub -q interactive -I -n 4 -R "rusage[mem=8000]" bash scripts/asic/run_vcs_unit.sh

# D VCS SoC
bsub -q interactive -I -n 4 -R "rusage[mem=16000]" bash scripts/asic/run_vcs_soc.sh

# E PT
cd work_t28
pt_shell -f ../scripts/asic/run_pt.tcl

# F Innovus（先改 SITE/电源名）
innovus -files ../scripts/asic/run_innovus.tcl -no_gui -log innovus.log
```

更短的库说明见 `scripts/asic/README_admin.md`。完成情况总表见 `reports/G_COMPLETION_STATUS.md`。
