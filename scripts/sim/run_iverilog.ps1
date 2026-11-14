# Windows 版 Icarus 三连，逻辑与 run_iverilog.sh 相同。
# 需要 iverilog、vvp 在 PATH 上。先在仓库根生成 hex。
#
# [给你看的对照] 刚学 Python 的话：
#   这是 PowerShell，不是 Python。$ 开头的是变量，function 相当于 def。
#   $PSScriptRoot  ≈  Path(__file__).parent（本脚本所在目录）
#   $ErrorActionPreference = "Stop"  ≈  失败就停，和 Python 的 sys.exit 同类
$ErrorActionPreference = "Stop"
# PSScriptRoot = scripts/sim → 上两级 = 仓库根
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

function Invoke-Sim($Name, $Tb) {
    Write-Host "== $Name =="
    $Out = Join-Path $env:TEMP "$Name.vvp"
    $Files = @(
        "rtl/core/rv32i_min.v",
        "rtl/bus/simple_interconnect.v",
        "rtl/mem/sram_1rw.v",
        "rtl/periph/uart_tx.v",
        "rtl/periph/tohost.v",
        "rtl/mvm/mvm_array_digital.v",
        "rtl/mvm/mvm_copro.v",
        "rtl/top/mvm_copro_top.v",
        "rtl/top/riscv_mvm_soc.v"
    )
    & iverilog -g2012 -o $Out -I rtl/include @Files $Tb
    if ($LASTEXITCODE -ne 0) { throw "iverilog failed: $Name" }
    & vvp $Out
    if ($LASTEXITCODE -ne 0) { throw "vvp failed: $Name" }
}

Invoke-Sim "tb_mvm" "tb/unit/tb_mvm_copro.v"
Invoke-Sim "tb_smoke" "tb/soc/tb_soc_smoke.v"
Invoke-Sim "tb_e2e" "tb/soc/tb_soc_e2e.v"
Write-Host "IVERILOG_ALL_PASS"
