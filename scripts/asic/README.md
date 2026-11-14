# 把协处理器接到 EDA2035 t28 数字全流程

题目要求报告**协处理器面积与访问延迟**，因此 ASIC DUT 用 `mvm_copro_top`，不要一上来综合整个带 8KB SRAM 的 SoC。

## 1. 拷到虚拟机

在 Windows 宿主机：

```powershell
scp -r .\riscv_mvm_e2e eda2035:/ic_proj/riscv_mvm_e2e
```

## 2. 用已有 t28 模板建工程

```bash
ssh eda2035
source ~/.tsmc28/env.sh
bash ~/Desktop/create_tsmc28_project.sh /ic_proj/mvm_copro_t28 mvm_copro_top tb_mvm_copro
```

然后把本仓库的 RTL 拷进工程：

```bash
cp /ic_proj/riscv_mvm_e2e/rtl/mvm/*.v     /ic_proj/mvm_copro_t28/rtl/
cp /ic_proj/riscv_mvm_e2e/rtl/top/mvm_copro_top.v /ic_proj/mvm_copro_t28/rtl/
cp /ic_proj/riscv_mvm_e2e/constraints/mvm_copro_top.sdc \
   /ic_proj/mvm_copro_t28/constraints/mvm_copro_top.sdc
```

`project.conf`：

```
DESIGN_NAME=mvm_copro_top
TESTBENCH_TOP=tb_mvm_copro
```

若模板 `run_dc.tcl` 只读一个 `rtl/${DESIGN_NAME}.v`，把三个文件拼进 filelist，或改成 `analyze` 多个 Verilog。

## 3. 跑主链路

```bash
cd /ic_proj/mvm_copro_t28
bash run_all.sh
bash scripts/check_outputs.sh
```

关注：

- `reports/dc/area.rpt` 或 DC log 里的 Area → 填 `reports/area_latency.md`
- `reports/pt/timing.rpt` 的 WNS。要求 uncertainty=4 ns 仍非负，即 50 MHz 下 ≥20% 裕量
- `results/innovus/mvm_copro_top.gds`

## 4. 访问延迟怎么填报告

RTL / 后仿都读 `MVM_LATENCY` 寄存器：

```
latency = settle + adc + 1 = 8 + 4 + 1 = 13 cycle
@50 MHz → 260 ns
```

再加总线写 6 个寄存器 + 轮询/中断的软件开销，在 SoC 仿真日志的 cycle 计数里量。

## 5. PVT

教学库若只有 tt0p9v25c，先在 TT 签 20% 裕量，报告里写明 corner 清单。有 ss/ff 再复跑 PT。
