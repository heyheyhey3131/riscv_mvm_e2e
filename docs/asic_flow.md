# ASIC 流程（t28）

详细命令见 `scripts/asic/README.md`。

最短路径：

1. DUT 用 `mvm_copro_top`（协处理器），不要先综合 8 KB RAM 的整 SoC。
2. 约束用 `constraints/mvm_copro_top.sdc`：50 MHz + 4 ns uncertainty = 20% 裕量。
3. 拷到 EDA2035 `/ic_proj`，套你已经跑通的 `create_tsmc28_project.sh`。
4. 从 DC area 与 `MVM_LATENCY` 填 `reports/TEMPLATE_area_latency.md`。

模拟版图（选做）：4×4 电阻阵列 + DAC/ADC 用 Virtuoso；数字控制器 P&R 后作为 macro 与阵列 floorplan 拼接。没有模拟 PDK 时，用 `tb/mixed` 的 real 模型交差即可，报告里写明边界。
