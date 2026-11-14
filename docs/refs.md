# 资料来源与许可证

本仓库的 RTL / 固件 / 教程是为题目 G 新写的教学代码。下面这些开源项目被 **对照过接口与结构**，没有整文件搬进 `rtl/`。

## RISC-V 核与 SoC

| 项目 | 地址 | 本仓库用了什么 |
|---|---|---|
| PicoRV32 | https://github.com/YosysHQ/picorv32 | native `mem_valid/ready` 时序、IRQ 思路、ISC 许可。可选 `scripts/vendor/fetch_picorv32.sh` |
| PicoSoC | 同上仓库 `picosoc/` | MMIO 译码、UART 作为外设、RAM ready 延一拍 |
| tinyriscv | https://github.com/liangkangnan/tinyriscv | 你已经跑过的教学核，本项目刻意用更短的多周期核方便读 |
| SERV | https://github.com/olofk/serv | 极小核参考，未采用（位串行不好接协处理器课） |

版图怎么做（数字 APR + 模拟 4×4）：`docs/mvm_layout_tutorial.md`。

## 模拟 / CIM

| 资料 | 地址 | 用了什么 |
|---|---|---|
| AnalogHub Verilog-A ADC/DAC | https://analoghub.ie/category/verilogModels/article/ADC | 均匀量化公式；本仓库 `analog/*.va` 按 6-bit/0.9V 重写 |
| DVCON SV real IMC | https://dvcon-proceedings.org/wp-content/uploads/1101-SystemVerilog-Real-Models-for-an-In-Memory-Compute-Design-1.pdf | 用 `real` 建模电流求和 |
| IBM analog IMC | https://research.ibm.com/blog/how-can-analog-in-memory-computing-power-transformer-models | 背景阅读 |
| 4-quadrant analog MVM | https://pmc.ncbi.nlm.nih.gov/articles/PMC11449787/ | 校准与符号表示背景 |

## 总线

PicoRV32 也提供 AXI4-Lite 与 Wishbone 封装。本项目为了第一周能仿真，用 valid/ready 原生口。若导师要求 AXI-Lite，可加一层 32-bit 从机（写寄存器的状态机与 `mvm_copro` 相同）。

## 许可

- 本仓库新代码：ISC（与 PicoRV32 同类，便于以后合入）
- PicoRV32：ISC
- AnalogHub 模型：以原站为准；本仓库未复制其源文件，只引用公式
