# 题目 G 代码与需求审计报告

日期：2026-11-15  
工程根：`riscv_mvm_e2e/`  
GitHub：`https://github.com/heyheyhey3131/riscv_mvm_e2e`（审计前基线 commit `040dbdf`）

## 1. 结论

**功能教学闭环已完成，项目要求尚未全部完成。**

已经能证明：

```
RISC-V 写 x/W → START → MVM → IRQ → 读回 y → |y-gold| ≤ 1 LSB → UART PASS
```

证据：`reports/iss_e2e.json`、`reports/copro_fsm.json`、`reports/precision.json`。  
没有完成：**VCS RTL 波形、DC 面积、PT 20% 裕量、Innovus DEF/GDS、AMS/模拟版图**。  
因此整体仍只能算「功能 + 方法学骨架」，不能按「全流程到版图」交差。

## 2. 题目条款逐项对照

| 条款 | 状态 | 证据 / 缺口 |
|---|---|---|
| RISC-V 核通过总线挂协处理器 | 代码完成 | `rtl/core/rv32i_min.v`、`rtl/bus/simple_interconnect.v` |
| 4×4 理想电流/电阻阵列 | 行为模型完成 | `rtl/mvm/mvm_array_digital.v`、`tb/mixed/mvm_array_real.sv`、`analog/mvm_array_4x4.va` |
| 6-bit ADC 行为模型 | 行为模型完成 | 量化 0..63；`analog/adc6.va` 未进 AMS |
| 寄存器接口 | 完成 | `docs/memory_map.md` |
| 写向量→MVM→ADC→读回→黄金比对 | ISS 通过 | `reports/iss_e2e.json`，三组向量，irq×3 |
| 总线读写/中断握手 | ISS + FSM 模型通过 | 缺 VCS/Verdi 波形 |
| MVM 误差 ≤ 1 LSB | 通过（理想 / 1% 失配） | `reports/precision.json` |
| t28 / 0.9 V | 库路径已对接，未综合 | `/home/xxypro/xyxue/Techlib/TSMC28` |
| PVT 接口裕量 ≥ 20% | 仅有 SDC 写法 | `uncertainty 4 ns @ 20 ns`；无 PT WNS |
| 协处理器面积/访问延迟 | 延迟有；面积无 | 13 cycle / 260 ns；无 DC area |
| 全流程到版图 | **未完成** | 无 DEF/GDS |
| 混合信号联合仿真 | 行为模型有；AMS 未跑 | `tb/mixed`、`analog/*.va` |

## 3. 本次发现并修复的逻辑不一致

### 3.1 UART 忙时仍返回 ready（会丢字符）— 已修

文件：`rtl/periph/uart_tx.v`

原实现：

```verilog
assign ready = valid;              // 即使 busy 也接收
if (wr_data && !busy) ...          // 忙时这次写被丢掉
```

CPU 连续 `putc('P')/putc('A')...` 时，后一个字符可能在 UART 忙时被静默丢弃。  
TB 监听总线写，所以 `PASS` 看起来正常，真实 `ser_tx` 不一定完整。

修复：写事务在 busy 时 `ready=0`，CPU 保持 valid；读 STATUS 仍可随时返回。

```verilog
assign ready = valid && ((wstrb == 4'b0000) || !busy);
```

代价：RTL SoC 的 UART 打印会变慢，`tb_soc_e2e` 的绝对周期数会增加；ISS 仍是瞬时 UART，所以 **ISS cycle 数不能直接当 RTL cycle 数**。功能判据不变。

### 3.2 RAM 地址译码范围大于实际 8 KB — 已修

文件：`rtl/bus/simple_interconnect.v`

原实现 `sel_ram = m_addr[31:16] == 16'h0000`，导致 `0x0000_2000..0x0000_FFFF` 全部别名到 8 KB RAM 的低位地址。ISS 只把前 8192 字节当 RAM，RTL 与 ISS 行为不一致。

修复：

```verilog
localparam [31:0] RAM_BYTES = 32'd8192;
wire sel_ram = m_valid && (m_addr < RAM_BYTES);
```

同时把 UART 收紧为 DATA/STATUS 两个精确地址，MVM 收紧为 256 字节窗口，TOHOST 精确地址。未映射地址仍立即 ready、读 0。

### 3.3 START 没有检查字节写使能 — 已修

文件：`rtl/mvm/mvm_copro.v`

原实现只看 `wdata[0]`，若写 CTRL 的高字节但数据 bit0 恰好为 1，也会误启动。  
修复：

```verilog
wire start_w = wr && (off == OFF_CTRL) && wstrb[0] && wdata[0];
```

### 3.4 C 固件没有开中断 — 已修

文件：`fw/src/main.c`、`fw/src/start.S`、`fw/Makefile`

C 版 `run_one()` 等待 `0x1F00` 由 IRQ handler 置位，但 `main()` 从未写 `mie`/`mstatus`。汇编版开了，C 版没开，C 固件会永远自旋。

修复：

- `main()` 调用 `enable_machine_irq()`，写 `mie.MEIE=1<<11`、`mstatus.MIE=1<<3`
- `fw/Makefile` 改用 `-march=rv32i_zicsr`（`csrw/mret` 需要）
- `start.S` 改用 `.text.start`，确保 `_start` 在 0x00、handler 在 0x10

C 版仍是可选路径；默认仿真仍是 `fw/asm/e2e_mvm.S`。

### 3.5 `mini_asm` 的 `jr` 伪指令错误 — 已修

文件：`fw/python/mini_asm.py`

原实现：

```python
return ["jalr", "x0", "0", a[0]]   # "0" 不是寄存器，编码会失败
```

修复为 `jalr x0, rs, 0`。新增 `scripts/sim/check_assembler.py` 固定检查 `lui/addi/sw/ret/jr/mret` 的机器码。

`li` 仍只支持 12-bit 立即数：本汇编器按「一条源指令 = 一个字」处理，不能自动变长成 `lui+addi`；大常数必须显式写两条。docstring 已写明。

### 3.6 `mvm_array_real` 的 MISMATCH 参数没有生效 — 已修

文件：`tb/mixed/mvm_array_real.sv`

原模块声明 `parameter real MISMATCH`，但计算里从未使用，容易让人误以为 mixed SV 仿真包含失配。  
失配实际由 `golden/mvm_ref.py` 的 `mvm_real()` 做 Monte Carlo；SV 模型改为理想实数阵列，删除未使用参数。

### 3.7 ISS 报告写绝对路径 — 已修

文件：`scripts/sim/iss.py`、`reports/iss_e2e.json`

原报告写 `D:\...\fw\hex\e2e_mvm.hex`，换机器不可复现。现在写相对仓库根路径 `fw/hex/e2e_mvm.hex`。

### 3.8 文档/脚本仍有 EDA2035 旧路径 — 已修

以下位置曾同时存在「inner-admin 是主环境」和「EDA2035 scp」两套说法：

- `README.md` 第 6 节
- `docs/asic_flow.md`
- `scripts/asic/README.md`
- `scripts/asic/project.conf` 注释
- `scripts/sim/run_vcs.sh` 注释

已统一为 inner-admin + LSF / `docs/next_steps_tutorial.md`。旧 EDA2035 命令不再作为主路径。

### 3.9 生成物污染工作区 — 已修

`run_all.py` 会生成 `*.pass1.txt` / `*.pass2.txt`。这些是调试中间件，不应进 Git。  
`.gitignore` 增加 `.idea/vcs.xml`、`*.pass1.txt`、`*.pass2.txt`。

## 4. 新增的自动回归

`python scripts/sim/run_all.py` 现在依次执行：

| 检查 | 作用 |
|---|---|
| `golden/mvm_ref.py` | 黄金向量 |
| `mini_asm.py` | 汇编 smoke/e2e |
| `iss.py` | RISC-V + MVM 端到端 |
| `check_assembler.py` | 固定机器码 / `jr` / `li` 边界 |
| `check_consistency.py` | C / RTL / Python 地址、量化、cfg 默认值 |
| `check_copro_fsm.py` | 13 拍 FSM + W1C |
| `check_precision.py` | 0/1%/5% 失配扫描 |

本次实际结果：

```
ISS_PASS ×2
ASSEMBLER_PASS
CONSISTENCY_PASS
COPRO_FSM_PASS latency=13 cycles @50MHz = 260 ns, W1C ok
PRECISION_PASS
```

## 5. 仍未完成（不是代码 bug，是环境和交付缺口）

| 项 | 说明 | 下一站 |
|---|---|---|
| VCS 单元/SoC 波形 | 上轮 RTL 解析成功后编译进程被 `Killed` | inner-admin `bsub -q interactive`，见 `docs/next_steps_tutorial.md` C/D |
| DC 面积 | 前台 DC 尚未成功产出 `area.rpt` | 交互登录 + `dc_shell -f scripts/asic/run_dc.tcl` |
| PT WNS | 依赖 DC 网表 | `run_pt.tcl` |
| Innovus DEF/GDS | 脚本已有，未成功跑 | `run_innovus.tcl`，先核对 SITE/电源名 |
| AMS / 模拟阵列版图 | 只有 Verilog-A 行为模型 | `docs/mvm_layout_tutorial.md` |
| PVT ss/ff | 只确认 TT 0.9 V 25C 库 | 先签 TT，报告中如实写明 |
| CPU 异常 | 未实现 ecall/ebreak trap、WFI 真正停机 | 题目 G 不要求；如要扩展再补 |

## 6. 项目要求的最终判断

- **功能演示**：可以
- **数字全流程作业**：不可以（缺 VCS/DC/PT/Innovus）
- **版图**：不可以（无 DEF/GDS；模拟阵列未画）
- **简历表述建议**：写「RISC-V + 4×4 MVM 行为级 SoC、ISS/FSM 验证、误差 ≤1 LSB、13 周期延迟」，不要写「已完成流片/签核」。
