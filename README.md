# 题目 G 教学工程：RISC-V + 4×4 模拟 MVM 协处理器

面向「第一次把 CPU、总线、协处理器、中断、黄金模型和数字全流程串起来」的读者。  
不需要先装 RISC-V GCC，不需要先开 Virtuoso。一台有 Python 3 的电脑就能看到 **PASS**。

---

## 0. 五分钟建立图像

你要做的不是一颗大 CPU，而是下面这张图：

```
        写 x、W          start           IRQ            读 y
RISC-V ----------> 寄存器组 ------> 4×4 阵列 ------> 6-bit ADC ------> RISC-V
                     MMIO           I=ΣV·G           量化 0..63         和黄金值比
```

对应课题组题目 G：

- 核：教学用多周期 RV32I（总线与 PicoRV32 兼容，可替换）
- 阵列：4×4 理想电流/电阻，先用整数模型，再用 real / Verilog-A
- ADC：6 bit
- 指标：误差 ≤ 1 LSB；总线和中断握手正确；端到端 PASS；PVT 接口裕量 ≥ 20%；给出协处理器面积和访问延迟

开源对照（详见 `docs/refs.md`）：

- [PicoRV32](https://github.com/YosysHQ/picorv32) / PicoSoC：总线与 MMIO 集成
- [AnalogHub ADC](https://analoghub.ie/category/verilogModels/article/ADC)：Verilog-A 量化公式
- DVCON SystemVerilog real IMC 模型：混合信号行为仿真

---

## 1. 目录（先认路，再读代码）

```
riscv_mvm_e2e/
  README.md                 ← 你在这里（教程）
  docs/                     架构、地址表、指标清单、引用
  rtl/core/                 CPU
  rtl/bus/                  地址译码
  rtl/mem/                  8 KB RAM 行为模型
  rtl/periph/               UART、tohost
  rtl/mvm/                  协处理器（这是题目的核心 IP）
  rtl/top/                  SoC 顶层、协处理器 ASIC 顶层
  analog/                   Verilog-A（Spectre 选做）
  fw/asm/                   真正拿来仿真的汇编
  fw/src/                   同算法的 C（给以后装 GCC 的人）
  fw/python/mini_asm.py     迷你汇编器，不依赖 RISC-V 工具链
  golden/mvm_ref.py         黄金模型
  tb/                       单元 / SoC / 混合
  scripts/sim/iss.py        Python 指令集仿真器（第一站）
  scripts/asic/             inner-admin × TSMC28 脚本（DC/VCS/PT/Innovus）
  docs/next_steps_tutorial.md  后续推进教程（DC→VCS→PT→数字版图）
  docs/mvm_layout_tutorial.md  MVM 版图：Innovus 生成方法 + 模拟阵列画法/资料
  constraints/              SDC
  reports/                  面积延迟报告模板
```

建议阅读顺序：本 README → `docs/memory_map.md` → `fw/asm/e2e_mvm.S` → `rtl/mvm/mvm_copro.v` → `rtl/core/rv32i_min.v`。

---

完成度与未完成清单见 **`reports/G_COMPLETION_STATUS.md`**（2026-11-02：inner-admin ISS 已过，工程在 `qjxiang/ic_proj/riscv_mvm_e2e`，t28 库已对接，版图未出）。

---

## 2. 第一站：30 分钟跑通（只需 Python）

在仓库根目录 `riscv_mvm_e2e/` 打开终端：

```powershell
python scripts/sim/run_all.py
```

它会：

1. 用 `golden/mvm_ref.py` 算出测试向量的 6-bit 结果  
2. 把 `fw/asm/*.S` 汇编成 `fw/hex/*.hex`  
3. 用 `scripts/sim/iss.py` 跑 CPU + 协处理器行为模型  

成功时看到（节选）：

```
wrote .../golden/vectors.json
  mixed            x=[40, 50, 60, 63] y=[33, 22, 16, 25] acc=[8520, 5720, 4260, 6390]
assembled .../smoke.S ... (4 words, last=0xc)
assembled .../e2e_mvm.S ... (252 words, last=0x3ec)
  00000000  _start
  00000010  irq_handler
tohost=1 cycles=3 instret=3 irq_seen=0
ISS_PASS
PASS
tohost=1 cycles=5658 instret=5655 irq_seen=3
ISS_PASS
COPRO_FSM_PASS  latency=13 cycles @50MHz = 260 ns, W1C ok
PRECISION_PASS
```

每一行是谁 print 的、数字怎么算出来的，对照 **`scripts/sim/run_all.py` 文件头的「终端输出对照表」**，以及对应脚本里 print 旁边的注释。

这已经覆盖题目里「RISC-V 写向量 → MVM → 读回比对」的**功能闭环**。  
RTL 波形和版图是后面的站，不是第一天的阻塞点。

只想确认汇编器：

```powershell
python fw/python/mini_asm.py fw/asm/smoke.S -o fw/hex/smoke.hex --map
python scripts/sim/iss.py fw/hex/smoke.hex
```

---

## 3. 数学：6-bit 电流型 MVM 到底在算什么

模拟侧（欧姆定律 + 基尔霍夫）：

\[
I_j = \sum_{i=0}^{3} V_i G_{ij}
\]

编码（都是 0…63）：

\[
V_i = \frac{x_i}{63}\times 0.6\,\mathrm{V},\quad
G_{ij} = w_{ij}\times 1\,\mu\mathrm{S}
\]

满量程电流对应「四个输入、四个权重全为 63」。数字侧不必算伏特，直接：

\[
\mathrm{acc}_j = \sum_i x_i w_{ij},\quad
y_j = \left\lfloor \mathrm{acc}_j / 252 \right\rfloor
\]

因为 \(4\times 63\times 63 = 15876\)，\(15876/63 = 252\)，所以 **满码进、满码出**。

自己算一道 mixed 向量（固件里第三组）：

```
x  = [40, 50, 60, 63]
W  = [[40,10,20,30],
      [40,20,20,30],
      [40,30,20,30],
      [40,40,20,30]]
acc = [8520, 5720, 4260, 6390]
y   = [33, 22, 16, 25]     # 即 8520/252 等
```

题目要 **误差 ≤ 1 LSB**：理想数字模型误差是 0；带失配的实数模型允许差 1 档。固件比较函数是 `|got-exp| <= 1`。

对应代码：

- Python：`golden/mvm_ref.py` 函数 `mvm_int`
- RTL：`rtl/mvm/mvm_array_digital.v`
- 固件：`fw/asm/e2e_mvm.S` 里的 `gold_pack` / `div252`

---

## 4. 软件视角：CPU 怎样驱动协处理器

地址表见 `docs/memory_map.md`。最小驱动程序（伪代码）：

```c
*(MVM_INP)   = pack(x0,x1,x2,x3);
*(MVM_WROW0) = pack(W[0][0]..W[0][3]);
// ... WROW1..3
*(MVM_CTRL)  = START | IRQ_EN;
while (*irq_flag == 0) ;          // 中断处理程序会置位
y = *MVM_OUTPACK;
assert(abs_bytes(y, y_gold) <= 1);
```

中断入口固定在 `0x10`（复位向量用两条指令 + 两条 nop 填满前 16 字节，这是刻意的，方便你在波形里对地址）。

handler 只做三件事：清 `MVM_IRQ`、写 `0x1F00=1`、`mret`。  
这就是题目说的「总线读写与中断握手」。

---

## 5. 硬件视角：三个状态机

### 5.1 CPU（`rv32i_min`）

多周期：取指 → 译码 → 执行 → （访存）→ 写回。  
每条指令在波形上能数拍，比流水线核适合当教材。

总线与 PicoRV32 相同：

```
mem_valid 保持到 mem_ready
读：wstrb=0
写：wstrb 为字节使能
```

中断在 **指令边界** 采样：`irq && mstatus.MIE && mie.MEIE`。

### 5.2 互联

```
addr[31:16]
  0000  RAM
  1000  UART
  2000  MVM
  3000  TOHOST
```

未映射地址立即 ready、读 0，CPU 不会死等。

### 5.3 协处理器 FSM

```
IDLE → SETTLE(N) → ADC(M) → DONE → IDLE
         默认 N=8        M=4
```

- `START` 是写脉冲，不占用 CTRL 存储位  
- `DONE` 时若 `IRQ_EN=1`，`irq` 变高直到软件 W1C  
- `LATENCY` 寄存器 = N+M+1，用来写报告，不必自己数波形  

访问延迟默认 **13 cycle × 20 ns = 260 ns**（50 MHz）。

---

## 6. 第二站：RTL 仿真（Icarus 或 VCS）

先生成 hex（第一站已经做过）。

**Icarus**（Windows 若已安装）：

```powershell
python scripts/sim/run_all.py --iverilog
```

或 Linux：

```bash
bash scripts/sim/run_iverilog.sh
```

**EDA2035 VCS：**

```bash
scp -r riscv_mvm_e2e eda2035:/ic_proj/
ssh eda2035
cd /ic_proj/riscv_mvm_e2e
bash scripts/sim/run_vcs.sh
```

三个 TB 的分工：

| TB | 证明什么 |
|---|---|
| `tb/unit/tb_mvm_copro.v` | 不经过 CPU，寄存器、延迟=13、IRQ、误差≤1 |
| `tb/soc/tb_soc_smoke.v` | CPU 能取指并写 TOHOST |
| `tb/soc/tb_soc_e2e.v` | 完整固件 + 中断次数 ≥ 3 + PASS |
| `tb/mixed/tb_mixed_sv.sv` | 实数电流模型 vs 整数模型 ≤ 1 LSB |

看波形时盯这几根线：`dut.u_cpu.pc`、`dut.irq_mvm`、`dut.u_mvm.state`、`dut.tohost`。

---

## 7. 第三站：混合信号（先 SV real，再 Verilog-A）

没有 Spectre 时，跑 `tb/mixed` 即可向导师说明：

- 数字控制器是真 RTL  
- 阵列是 `I = V·G` 的实数模型  
- ADC 是均匀量化  
- 与整数黄金值差不超过 1 LSB  

有 Virtuoso 时，按 `analog/README.md` 把 `dac6.va`、`mvm_array_4x4.va`、`adc6.va` 建成 cell，和 `mvm_copro` 做 AMS。权重第一版可以用 Verilog-A parameter，打通后再改成电气端口。

---

## 8. 第四站：t28 数字全流程

ISS 已经通过、工程已在 inner-admin 之后，**不要再读 EDA2035 那套拷贝说明**。  
按站推进（DC → LSF+VCS → PT → Innovus → 填报告）见：

**`docs/next_steps_tutorial.md`**

要点只有三条：

- DUT 用 `mvm_copro_top`，不要把 8 KB 行为 RAM 丢进 Innovus
- 约束：20 ns 时钟 + 4 ns uncertainty（= 50 MHz 下 20% 裕量）
- 工艺库只读 `/home/xxypro/xyxue/Techlib/TSMC28`，工程写在 `qjxiang/ic_proj/riscv_mvm_e2e`

---

## 9. 关键源码怎么读（故意写短）

从这些函数/always 块入手，不要从头到尾扫三千行：

1. `mvm_array_digital.v` 里四行 `assign y0 = quant6(...)`  
2. `mvm_copro.v` 里 `ST_SETTLE / ST_ADC`  
3. `e2e_mvm.S` 的 `_start`（0x00）、`irq_handler`（0x10）、`run_one`  
4. `rv32i_min.v` 的 `S_FETCH` 和 `S_IRQ`  
5. `iss.py` 的 `MvmModel.start` —— 和 RTL 同一套量化

CPU 若暂时读不懂，不影响做协处理器；ISS 已经能跑固件。

---

## 10. 和 PicoRV32 的关系

默认核是 `rv32i_min`（约 400 行，中文注释），原因：

- 你要交的是 **协处理器 + 全流程**，不是再实现一个工业核  
- 总线时序故意与 PicoRV32 相同  

以后要写进简历「基于 PicoRV32」：

```bash
bash scripts/vendor/fetch_picorv32.sh
```

按 `third_party/README.md` 替换例化。PicoRV32 的中断是自定义 `retirq`，固件 handler 要改；**MVM 寄存器一比特都不用动**。

---

## 11. 常见卡住点

**ISS 报 illegal inst**  
汇编器没认出指令。看 `mini_asm.py` 支持列表，或用 `--map` 看标签地址。

**一直等中断**  
检查是否写了 `IRQ_EN`、是否 `csrw mie/mstatus`、handler 是否在 `0x10`。波形里 `irq` 若已高而 `pc` 不到 `0x10`，是 CPU 中断使能问题。

**结果差很多，不止 1 LSB**  
字节顺序：小端，`WROW_i` 的 byte0 对应输出 y0。用 `golden/mvm_ref.py` 先打印 `y=`。

**综合报 RAM**  
你综合了 `riscv_mvm_soc`。改用 `mvm_copro_top`。

**没有模拟 PDK**  
用 `tb/mixed` + 本 README 第 7 节说明行为模型边界，仍然满足题目「理想阵列 + ADC 行为模型」。

---

## 12. 指标速查

完整表：`docs/checklist.md`。

| 项 | 本仓库默认值 |
|---|---|
| 工艺目标 | t28 0.9 V |
| 阵列 | 4×4 |
| ADC | 6 bit |
| 量化 | `sum(x*w)//252` |
| 延迟 | 13 cycle @ 50 MHz = 260 ns |
| 误差 | 理想 0 LSB，比较器允许 1 LSB |
| 中断 | 电平，W1C，mtvec=0x10 |

---

下一步：先跑第 2 节的 `run_all.py`。通过之后，再打开 `docs/architecture.md` 对照波形。
