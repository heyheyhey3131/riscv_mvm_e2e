# third_party

> 刚学 Python 的你：这里默认是空的。日常 ISS 用的是仓库自己的 `rtl/core/rv32i_min.v` 和 `scripts/sim/iss.py`，不必 clone。

默认 **不** 包含 PicoRV32 源码（约三千行），避免第一周被工业核淹没。

需要替换 CPU 时：

```bash
bash scripts/vendor/fetch_picorv32.sh
```

然后在 `rtl/top/riscv_mvm_soc.v` 把 `rv32i_min` 换成：

```verilog
picorv32 #(
    .ENABLE_IRQ(1),
    .ENABLE_COUNTERS(0),
    .PROGADDR_RESET(32'h0000_0000),
    .PROGADDR_IRQ  (32'h0000_0010),
    .STACKADDR     (32'h0000_2000)
) u_cpu ( ... mem_* ... irq );
```

注意：PicoRV32 的 IRQ 不是标准 `mret/mie`，固件 handler 要改成它的 `retirq/maskirq` 自定义指令。协处理器 MMIO **不用改**。
