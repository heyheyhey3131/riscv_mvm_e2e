# MVM 版图教程：数字控制器 + 4×4 模拟阵列

题目 G 的「全流程到版图」其实是 **两块版图**，不要合成一件事：

```
┌─────────────────────────────────────────────────────────┐
│  芯片顶层（可选，后期再拼）                                │
│  ┌──────────────────────┐   ┌─────────────────────────┐ │
│  │ 数字：mvm_copro_top   │   │ 模拟：4×4 阵列 + DAC/ADC │ │
│  │ Innovus 标准单元      │   │ Virtuoso 全定制 / 宏     │ │
│  │ 已有 run_innovus.tcl  │   │ 本文件主讲                │ │
│  └──────────────────────┘   └─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

题目原文写的是「理想电流/电阻阵列 + 6-bit ADC **行为模型**」。  
所以：**数字控制器必须有版图；模拟阵列可以先行为模型，再升级成多边形。**  
导师若点名「要看到阵列」，用下面路 B 或路 C，不必做成 6-bit 可编程的工业 CIM。

工艺：TSMC 28HPC+，0.9 V。  
模拟 PDK：`/home/xxypro/xyxue/Techlib/TSMC28/tsmc28hpc/`（`tsmcN28`、`models/`、`cds.lib`）。  
数字库：`.../T28HPC+IP/tcbn28hpcplusbwp30p140_190a/`。  
你的可写目录：`/home/xxypro/xyxue/Members/qjxiang/`（Virtuoso 库建在这里，**不要写进 Techlib**）。

数字 APR 的命令级步骤仍以 `docs/next_steps_tutorial.md` 第 F 站为准。本文补：**版图生成方法、阵列怎么画、资料从哪找、怎么和数字拼。**

---

## 0. 先选一条路（工作量差一个数量级）

| 路 | 你交出去的版图 | 工作量 | 和题目的关系 |
|---|---|---|---|
| **L0 数字 only** | 只有 `mvm_copro_top` 的 Innovus DEF/截图 | 1 天 | 满足「协处理器面积」；阵列仍是 RTL/VA 行为模型 |
| **L1 占位宏** | 数字 + 一块空 analog abstract（LEF 黑盒） | +0.5 天 | 顶层 floorplan 能讲「阵列在左边」 |
| **L2 固定电阻阵列** | Virtuoso 画出 4×4 电阻（权重硬连 mixed 向量） | +1–2 天 | 有真实多边形，对应「理想电阻阵列」 |
| **L3 可编程 cell** | 每格 6-bit 开关+电阻或线性区 MOS | +1–2 周 | 才像论文 CIM，远超题目最低要求 |

推荐交差组合：**L0 必做 + L2 加分**。L3 只有导师明确要求可编程模拟权重时再做。

---

## 1. 数字 MVM 控制器版图（Innovus 生成）

### 1.1 生成方法

这是 **自动生成**，不是手画：

```
RTL (mvm_copro_top)
  → DC 网表  work_t28/results/mvm_copro_top.syn.v
  → Innovus  scripts/asic/run_innovus.tcl
  → DEF / ENC / 面积报告
```

脚本已经写好。登录 inner-admin、license 有效后：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/work_t28
# 先确认 DC 网表在
ls results/mvm_copro_top.syn.v results/mvm_copro_top.syn.sdc
grep SITE  .../tcbn28hpcplusbwp30p140.lef | head
bsub -q interactive -I -n 4 -R "rusage[mem=16000]" \
  innovus -files ../scripts/asic/run_innovus.tcl -no_gui -log innovus.log
```

成功：`INNOVUS_DONE`，`results/mvm_copro_top.def`。

细节（SITE、电源名、tlef）见 `docs/next_steps_tutorial.md` §7。

### 1.2 为以后拼模拟宏，引脚怎么摆

现在脚本没有 `editPin`。若你要走 L1/L2，在 `placeDesign` **之前**加（按实际 SITE 改边）：

```tcl
# 模拟宏在芯片左侧：把会接到阵列的总线脚挤到左边
set analog_pins {valid ready addr wdata wstrb rdata irq}
editPin -spreadType RANGE -side LEFT -start {0 5} -end {0 40} \
        -layer M4 -pin $analog_pins -fixedPin 1
editPin -spreadType RANGE -side BOTTOM -pin {clk rst_n} -fixedPin 1
```

电源环脚本用 M8/M9。若 tlef 是 9LM 6X2R，顶层金属名以 tlef 为准（有的叫 `AP`/`RDL` 而不是 `M9`）。`addRing` 报层名就 `lef -layer` 看一层再改。

### 1.3 看版图

```tcsh
cd work_t28
innovus -init results/mvm_copro_top.enc
```

截图：floorplan 全景、电源环、标准单元密度。面积从 `reports/innovus_area.rpt` 抄。

GDS：没有 layer map 先不要 `streamOut`。教学作业 DEF + 截图即可。组里若有 `gds2.map`，再补。

---

## 2. 模拟 4×4 阵列：物理图像

数字侧在算：

\[
y_j=\left\lfloor\frac{\sum_i x_i w_{ij}}{252}\right\rfloor
\]

模拟侧应对：

\[
I_j=\sum_{i=0}^{3} V_i G_{ij},\quad
V_i=\frac{x_i}{63}\times 0.6\,\mathrm{V},\quad
G_{ij}=w_{ij}\times 1\,\mu\mathrm{S}
\]

列电流经 \(R_T\approx 3.97\,\mathrm{k}\Omega\) 变成 0–0.6 V，再 6-bit ADC。

一张图：

```
  x0──DAC──V0 ──┬── G00 ──┬── G01 ──┬── G02 ──┬── G03
  x1──DAC──V1 ──┼── G10 ──┼── G11 ──┼── G12 ──┼── G13
  x2──DAC──V2 ──┼── G20 ──┼── G21 ──┼── G22 ──┼── G23
  x3──DAC──V3 ──┴── G30 ──┴── G31 ──┴── G32 ──┴── G33
                 │         │         │         │
                ΣI0       ΣI1       ΣI2       ΣI3
                 │         │         │         │
                R_T       R_T       R_T       R_T
                 │         │         │         │
                ADC0      ADC1      ADC2      ADC3   → y0..y3
```

版图上就是：**行是电压总线，列是电流求和树，交叉点是电导。**

电阻取值（路 L2 硬连 mixed 向量时）：

| \(w\) | \(G=w\cdot 1\mu\mathrm{S}\) | \(R=1/G\) |
|---|---|---|
| 1 | 1 µS | 1 MΩ |
| 10 | 10 µS | 100 kΩ |
| 40 | 40 µS | 25 kΩ |
| 63 | 63 µS | 15.87 kΩ |

**方阻不要上网抄。** 打开 PDK 电阻模型看 `rsh`，用 \(R = R_\mathrm{sh}\times L/W\) 反推 L/W。28HPC 非硅化 poly 电阻方阻通常几百 Ω/□，1 MΩ 会很长，所以 L2 更合理的做法是：**把 \(G_\mathrm{unit}\) 改成 10–50 µS，按比例改 \(R_T\)**，阵列面积才画得下。改完必须同步 `golden/mvm_ref.py` 的满量程，或只把版图当示意、量化仍走数字模型。

---

## 3. 路 L1：占位宏（最快让顶层「有阵列」）

不画晶体管，做一个 **abstract LEF**，Innovus 当 hard macro 摆。

1. 在 Virtuoso 新建库（路径在 `qjxiang` 下），cell `mvm_array_macro`，view `layout`
2. 画一个矩形边界，例如 80 µm × 80 µm，四边放 pin：`VIN<3:0>`、`VOUT<3:0>`、`VDD`、`VSS`
3. 导出 LEF（Virtuoso Abstract Generator，或手写最小 LEF）
4. Innovus：`init_lef_file` 加上这个 LEF，`placeInstance` 放到 core 左边，数字标准单元 `placeDesign` 避开

最小 LEF 骨架（尺寸按你画的改）：

```
VERSION 5.8 ;
BUSBITCHARS "<>" ;
DIVIDERCHAR "/" ;
MACRO mvm_array_macro
  CLASS BLOCK ;
  ORIGIN 0 0 ;
  FOREIGN mvm_array_macro 0 0 ;
  SIZE 80 BY 80 ;
  PIN VIN<0>  DIRECTION INPUT ;  PORT ; LAYER M4 ; RECT 0 10 0.2 10.2 ; END  END VIN<0>
  PIN VDD     DIRECTION INOUT ; USE POWER ; PORT ; LAYER M4 ; RECT 0 70 80 72 ; END  END VDD
  PIN VSS     DIRECTION INOUT ; USE GROUND ; PORT ; LAYER M4 ; RECT 0 8 80 10 ; END  END VSS
END mvm_array_macro
END LIBRARY
```

报告里写清楚：这是 **floorplan 占位**，不是提取过的模拟版图。

---

## 4. 路 L2：Virtuoso 固定电阻阵列（推荐的「真版图」）

权重 **硬连** 成 `golden/vectors.json` 的 `mixed` 组（或全 63 的满量程示意）。  
数字控制器仍然可编程；模拟多边形只证明「交叉点是电阻、列是电流和」。

### 4.1 建库（只写 qjxiang）

VNC 登录 inner-admin，开 IC618。自己的 `cds.lib` 放在例如：

```
/home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/analog/cadence/cds.lib
```

内容结构：

```
INCLUDE /home/xxypro/xyxue/Techlib/TSMC28/tsmc28hpc/cds.lib
DEFINE mvm_ana /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/analog/cadence/mvm_ana
```

`DEFINE` 的目录要你自己 `mkdir`。不要改 Techlib 里的 `cds.lib`。

启动：

```tcsh
cd /home/xxypro/xyxue/Members/qjxiang/ic_proj/riscv_mvm_e2e/analog/cadence
virtuoso &
```

Library Manager 里应能看到 PDK 库（常见名 `tsmcN28` 或类似）和空的 `mvm_ana`。

### 4.2 找电阻器件（不要猜 cell 名）

在 PDK 库里搜关键字（Library Manager 的 filter）：

- `rppoly` / `nrpoly` / `prpoly` / `rnod` — 非硅化 poly 电阻（匹配好，优先）
- `rm1` / `rmetal` — 金属电阻（方阻小，高阻难做）
- 文档：`/home/xxypro/xyxue/Techlib/TSMC28/tsmc28hpc/PDK_doc/` 和 `ReleaseNote.txt`

打开电阻 symbol → CDF 看 **sheet resistance、最小 W/L、dummies**。  
用 \(L/W = R / R_\mathrm{sh}\) 算尺寸。W 用 PDK 允许的最小宽度的 2–3 倍，匹配更好。

找不到独立电阻时的退路：用 **线性区 NMOS** 当电导（栅极接固定偏置或接 DAC 电压）。这已经接近路 L3，但 4×4=16 管，版图仍很小。

### 4.3 原理图

Cell：`mvm_array_4x4_sch`

- 4 根水平 `VIN<i>`
- 4 根垂直 `IOUT<j>`（或直接接到 `R_T` 再出 `VOUT<j>`）
- 16 个电阻，连在交叉点：一端 VIN，一端 IOUT
- 4 个 `R_T`（可用同一电阻类型，约 4 kΩ 量级，按你的满量程改）
- 电源：若只有无源电阻，顶层仍要 `VDD/VSS` 给以后的 DAC/ADC 留脚

`mixed` 向量的 \(W\) 是：

```
[[40,10,20,30],
 [40,20,20,30],
 [40,30,20,30],
 [40,40,20,30]]
```

对应 16 个不同阻值。可以：

- 16 个不同 L 的电阻（简单，匹配差）
- **单位电阻并联**：先定 \(R_u=100\,\mathrm{k}\Omega\) 对应 \(w=10\)，则 \(w=40\) 用 4 个并联。版图整齐，推荐

### 4.4 版图生成方法（Layout XL，不要纯手画 16 个）

1. 原理图 Check and Save
2. Launch → Layout XL → Create New
3. **Generate All From Source**（先出 instance）
4. 先摆 **单位电阻** 的一格，做成 `g_cell`（有源区、dummy、两头接触）
5. 用 **array / copy by pitch** 铺 4×4；并联的用相邻复制
6. 行线用同一层金属横穿，列线用上一层竖穿，交叉通孔对齐
7. 列电流线 **等长、等宽、对称**（否则 INL 就是布线电阻）
8. 四周一圈 dummy 电阻，不接线，只为刻蚀均匀
9. Pin：`VIN<3:0>`、`VOUT<3:0>`、`VDD`、`VSS` 放到边界，方便以后当宏

匹配要点（Hastings《The Art of Analog Layout》第 7、12 章那套）：

- 同向放置，不要一个横一个竖
- 公共重心：4×4 很难完美 common-centroid，至少 **左右镜像 + 上下 dummy**
- 不要在阵列上跨宽电源线；电源从两侧走
- 电阻头部接触个数一致

### 4.5 DRC / LVS / 提参

规则在 PDK 的 Calibre 或 Assura 目录（`tsmc28hpc/Calibre*`、`QCI`）。  
用 **组里已经跑通的 28HPC 电阻例程** 的 rule deck，不要自己找最新 foundry 包。

流程：

```
Layout XL 连线完成
  → Calibre DRC（先过 density / spacing）
  → Calibre LVS（对照原理图）
  → PEX（C+CC 即可，教学不必全 R+C）
  → Spectre 读 extracted，看四列电流是否接近黄金值
```

误差目标仍是 **≤ 1 LSB**。提取后很容易超：先查列线电阻、再查 dummy 是否真的没连进网表。

### 4.6 和 Verilog-A 的关系

L2 画完后，仿真有两条：

- **原理图 + 理想 VA ADC**：证明电阻网络对
- **extracted + 数字 `mvm_copro`**（AMS）：证明和控制器握手

行为模型 `analog/mvm_array_4x4.va` **继续留着**当黄金对照，不要删。

---

## 5. 路 L3：可编程交叉点（仅在需要时）

每格要随 6-bit \(w\) 变电导。常见三种，论文里都有：

| 结构 | 做法 | 版图 |
|---|---|---|
| 二进制加权电阻 + MOS 开关 | 6 个电阻 \(R,2R,\ldots,32R\) 并联，开关选通 | 每格 6 开关 + 6 电阻 |
| 温度计 63 个单位电阻 | 匹配最好 | 面积大 |
| 线性区 MOS（伪跨导） | 栅极接 DAC 电压或偏置，沟道当 \(G\) | 每格 1 管，最小；线性差 |

教学若做 L3，用 **二进制加权 + 最小开关**，先做 **一格** 仿真合格，再 array。

开关用 PDK 的 `nch`（搜 `nch_lvt` / `nch_mac`）。注意：开关导通电阻会吃掉权重，要 \(R_\mathrm{on}\ll R_\mathrm{LSB}\)，或用 CMOS 传输门。

数字权重线 16×6=96 根，从 `mvm_copro` 寄存器到阵列，这是 **数字到模拟的真正接口**。Innovus 侧要预留 bus pin；模拟侧用 M3/M4 做屏蔽，远离列电流线。

---

## 6. DAC / ADC 版图（6-bit，别做成题目 A）

题目只要 **行为级 ADC**。版图加分可以极简：

**DAC（输入 \(x\)）**

- 最简：6-bit 电阻串 + 开关（电压型），输出 0–0.6 V
- 资料：Razavi《Data Conversion System Design》电阻串 DAC；Baker CMOS 混合信号书第 28 章

**ADC（列电压）**

- 最简：6-bit 电阻串 Flash 的一半——其实 Flash 面积大
- 教学可用：**单斜率**（电容充电 + 数字计数）几乎全是数字，模拟只有一个比较器
- 比较器：题目 I 才是「StrongARM + 校准」。这里用 PDK 反相器链或现成 comparator 例程即可

时间预算已经写在数字 FSM 里：`settle=8`、`adc=4` 拍 @ 50 MHz → 160 ns / 80 ns。模拟建立必须短于这个数，否则加大 `MVM_CONFIG`。

---

## 7. 数字 + 模拟怎么拼（混合信号顶层）

```
          VDD  ring
    ┌─────┴──────────────────────────┐
    │  analog 4x4     │  digital APR  │
    │  (Virtuoso GDS) │  (Innovus)    │
    │  VIN/VOUT 西侧  │  总线脚朝西   │
    └─────────────────┴──────────────┘
```

两种拼法：

1. **Innovus 读 analog LEF 当 hard macro**（路 L1/L2 导出 abstract）  
   `placeInstance mvm_array_macro 5 5 -fixed`  
   再 `placeDesign` 数字。电源 `addStripe` 跨过两块。
2. **Virtuoso 顶层** 把 Innovus GDS 当 instance 推进去（需要 GDS + 层图）。教学成本高，放最后。

隔离：模拟地与数字地在 pad 上单点汇；阵列下面不要走时钟。CTS 把时钟树限制在数字区（`createClockGroup` / 不要给 analog pin 做时钟树）。

---

## 8. 资料来源（版图能直接用的）

### 8.1 工艺与工具（你机器上已有）

| 东西 | 路径 / 工具 |
|---|---|
| 数字 stdcell LEF/LIB | `Techlib/TSMC28/T28HPC+IP/tcbn28hpcplusbwp30p140_190a/` |
| 数字 tech LEF | `Techlib/TSMC28/N28_PRTF_Cad_v1d5a/PR_tech/Cadence/LefHeader/HVH/*.tlef` |
| 模拟 iPDK | `Techlib/TSMC28/tsmc28hpc/`（`tsmcN28`、`models/`、`PDK_doc/`） |
| Virtuoso | inner-admin `IC618` |
| Innovus | `INNOVUSEXPORT21.39` |
| Calibre | mentor calibre 在 PATH 里 |
| 本仓库 VA 模型 | `analog/*.va` |
| 本仓库数字 APR | `scripts/asic/run_innovus.tcl` |

### 8.2 书（匹配、电阻、混合信号）

- Alan Hastings, *The Art of Analog Layout* — dummy、common-centroid、电阻头部
- Razavi, *Design of Analog CMOS Integrated Circuits* — 电流镜/匹配（列求和若加电流镜时）
- Razavi, *Principles of Data Conversion System Design* — 电阻串 DAC、量化
- Baker, *CMOS Circuit Design, Layout, and Simulation* — 电阻、开关、简单 ADC
- 陈贵灿 / 国内《模拟 CMOS》实验讲义里的「电阻匹配」章节（有中文图）

### 8.3 论文 / 笔记（CIM 阵列版图长什么样）

不必复现它们的器件，只看 **交叉点 + 列求和 + ADC 摆放**：

| 资料 | 看什么 |
|---|---|
| [IBM analog IMC 博客](https://research.ibm.com/blog/how-can-analog-in-memory-computing-power-transformer-models) | 电流型 MVM 系统图 |
| [4-quadrant analog MVM (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11449787/) | 校准、符号、列 ADC |
| DVCON *SystemVerilog Real Models for an In-Memory Compute Design* | 行为模型怎么和版图分区 |
| ISSCC / JSSC 搜 `analog in-memory computing capacitor DAC` | 交叉点版图照片（电容型更多，电阻型同拓扑） |
| AnalogHub ADC/DAC VA | 量化公式（已写入 `analog/dac6.va`） |

开源版图参考（不是 t28，只看结构）：

- SkyWater 130 开源 PDK 的电阻/DAC 例（Google/SkyWater + Tiny Tapeout 里的 `dac` cell）
- IHP SG13G2 开源 PDK 电阻器件文档

### 8.4 组内

先问有没有 **已经过 DRC 的 28HPC 电阻/DAC 例程**。有的话 L2 直接抄 cell 再 array，比从零画安全。

---

## 9. 建议你实际怎么做（按周）

**第 1 段（必须）——数字版图**

1. `docs/next_steps_tutorial.md` 把 DC、Innovus 跑通  
2. 截 Innovus 顶视图，填 `area_latency.md` 的数字面积  

**第 2 段（加分，推荐）——L2 电阻阵列**

1. `qjxiang` 下建 `mvm_ana` 库  
2. 画 1 个单位电阻，DRC 过  
3. Layout XL 铺 4×4 + 列 \(R_T\)  
4. LVS；Spectre 对 mixed 向量看四列电压  
5. 截阵列版图，报告里写「固定电导示意，可编程权重在数字模型」  

**第 3 段（可选）**

- L1 abstract 把阵列宏推进 Innovus  
- 或 Verilog-A AMS 联仿（`analog/README.md`）  

不要一上来画 6-bit×16 的可编程电阻 DAC，那会把 G 题做成另一道全定制题。

---

## 10. 报告里版图怎么写

数字：

- 工具：Innovus 21，库 BWP30P140 TT 0.9 V  
- 面积：`innovus_area.rpt`  
- 产物：DEF 路径、截图  

模拟（若做了 L2）：

- 器件：PDK 电阻名、\(R_\mathrm{sh}\)、单位 \(W/L\)  
- 阵列：4×4，dummy 一圈，列金属层  
- DRC/LVS：过 / 未过（未过就写剩余 violation 类型）  
- 明确一句：**可编程 MVM 精度指标仍由数字/VA 模型保证；多边形阵列是物理示意**

---

## 11. 和其它文档的分工

| 文档 | 管什么 |
|---|---|
| `docs/next_steps_tutorial.md` | DC / VCS / PT / Innovus **命令** |
| **本文** | MVM **版图生成方法、阵列怎么画、资料** |
| `analog/README.md` | Verilog-A 仿真约定 |
| `scripts/asic/run_innovus.tcl` | 数字 APR 脚本 |
| `reports/area_latency.md` | 往里填面积 |

命令备忘仍在 `next_steps_tutorial.md` 第 12 节。版图怎么从网表长出来、阵列怎么从电阻长出来，以本文为准。
