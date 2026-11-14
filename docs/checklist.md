# 题目 G 指标对照

| 指标 | 状态 (2026-11-02) | 证据 / 还缺 |
|---|---|---|
| t28, 0.9 V | 库已对接 inner-admin Techlib，综合未出报告 | `/home/xxypro/xyxue/Techlib/TSMC28`；`run_dc.tcl` |
| 4×4 阵列 | 行为模型完成 | digital / real / Verilog-A；无晶体管版图 |
| 6-bit ADC | 行为模型完成 | 量化 0..63；AMS 未跑 |
| MVM 误差 ≤ 1 LSB | **通过**（理想与 1% 失配） | `reports/precision.json`；5% 失配会破 1 LSB |
| 总线读写正确 | ISS/FSM 通过 | 缺 HDL 波形 |
| 中断握手正确 | **ISS 通过** 三次 start→irq(+13)→W1C | `reports/iss_e2e.json`；缺 Verdi |
| RISC-V 端到端通过 | **ISS 通过** `PASS`（本机 + inner-admin） | VCS 解析过 RTL 后被 Killed |
| PVT 接口裕量 ≥ 20% | 仅有 SDC | 缺 PT WNS |
| 协处理器面积 | 未测 | DC 脚本已就位，需登录环境跑 |
| 访问延迟 | **13 cycle / 260 ns @50 MHz** | `reports/copro_fsm.json`；缺后仿 |

总报告：`reports/G_COMPLETION_STATUS.md`

## 建议的提交物

1. 本仓库（RTL、固件、TB、黄金模型、教程）
2. `reports/area_latency.md`（DC 面积 + latency 寄存器 + 时序 WNS）
3. 波形截图：start → irq → mret → 读 OUTPACK
4. （可选）Innovus GDS 截图
5. （可选）Verilog-A AMS 仿真
