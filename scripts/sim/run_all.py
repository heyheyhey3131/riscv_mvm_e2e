#!/usr/bin/env python3
"""一键跑通题目 G 的软件侧闭环。

流水线（每一步失败就停，不继续往后）：

    1. golden/mvm_ref.py      算出 4x4 MVM 测试向量的 6-bit 黄金结果
    2. fw/python/mini_asm.py  把汇编编成 $readmemh 用的 hex
    3. scripts/sim/iss.py     用 Python 指令集仿真器跑 CPU + 协处理器
    4. check_copro_fsm.py     周期精确核对协处理器 FSM（latency=13）
    5. check_precision.py     整数 / 实数 / 失配扫描，误差 ≤ 1 LSB
    6. （可选 --iverilog）    再调 Icarus 跑 RTL testbench

为什么第一站是 Python ISS，而不是 VCS / Icarus？
    本机不一定装了 Verilog 仿真器，也不一定有 RISC-V GCC。
    ISS 只依赖 Python 3，用来证明：汇编器、固件算法、中断、黄金比对是通的。
    RTL 波形是下一站，不要让工具链挡住理解。

用法（在仓库根目录 riscv_mvm_e2e/ 下）：

    python scripts/sim/run_all.py              # 黄金向量 + 汇编 + ISS
    python scripts/sim/run_all.py --smoke-only # 只跑冒烟固件（CPU 写 TOHOST=1）
    python scripts/sim/run_all.py --iverilog   # 上面全部做完后，再跑 Icarus RTL

成功判据：
    smoke  : 打印 ISS_PASS，tohost=1
    e2e    : 打印 PASS、ISS_PASS，tohost=1，irq_seen=3
    FSM    : 打印 COPRO_FSM_PASS
    精度   : 打印 PRECISION_PASS（5% 失配那一行允许 FAIL，不算总失败）

================================================================
终端输出对照表（默认 python scripts/sim/run_all.py，无 --iverilog）
================================================================

本脚本自己只打印以 "+ " 开头的命令回显（见 run()）。其余每一行都是
某个子进程的 stdout，失败时该子进程非 0 退出，本脚本立刻 sys.exit。

下面按屏幕从上到下排列。路径会随本机 Python / 仓库位置变化，数字是固定的。

---- 步骤 1：golden/mvm_ref.py --------------------------------
+ <python> .../golden/mvm_ref.py
    本文件 run() 打印。后面 5 行来自 mvm_ref.py 的 main()。

wrote .../golden/vectors.json
    mvm_ref.py: json.dumps(annotate(VECTORS)) 写文件后的确认。
    annotate() 给每组向量补上 y、acc，公式 y = (Σ x_i*w_ij) // 252。

  zeros            x=[0, 0, 0, 0] y=[0, 0, 0, 0] acc=[0, 0, 0, 0]
  fullscale        x=[63, 63, 63, 63] y=[63, 63, 63, 63] acc=[15876, 15876, 15876, 15876]
      4*63*63=15876，15876//252=63，满码进满码出。
  mixed            x=[40, 50, 60, 63] y=[33, 22, 16, 25] acc=[8520, 5720, 4260, 6390]
      acc0=40*40+50*40+60*40+63*40=8520 → 8520//252=33
      acc1=40*10+50*20+60*30+63*40=5720 → 22
      acc2=40*20+50*20+60*20+63*20=4260 → 16
      acc3=40*30+50*30+60*30+63*30=6390 → 25
  identity_like    x=[16, 32, 48, 63] y=[4, 8, 12, 15] acc=[1008, 2016, 3024, 3969]
      对角权重 63：16*63=1008//252=4，…，63*63=3969//252=15（不是 16，因为向 0 取整）

---- 步骤 2a：汇编 smoke.S ------------------------------------
+ <python> .../mini_asm.py .../smoke.S -o .../smoke.hex
assembled .../smoke.S -> .../smoke.hex  (4 words, last=0xc)
    mini_asm.py main()：4 条机器字 = lui / addi / sw / jal(hang)，
    最后一条地址 0x0C（见 fw/asm/smoke.S）。

---- 步骤 2b：汇编 e2e_mvm.S（带 --map）-----------------------
+ <python> .../mini_asm.py .../e2e_mvm.S -o .../e2e_mvm.hex --map
assembled .../e2e_mvm.S -> .../e2e_mvm.hex  (252 words, last=0x3ec)
    252 个非空字；最后一条 write_tohost 落在 0x3E4，机器字末地址 0x3EC。
  00000000  _start          复位向量，必须在 0x00
  00000010  irq_handler     mtvec 固定 0x10，CPU 中断入口
  00000048  main            开 mie/mstatus，跑三组向量
  00000110  hang            PASS 之后死循环
  00000114  fail            UART 打 'F'，TOHOST=3
  ...                       其余标签是子程序：run_one / gold_pack / mul_u / div252 / putc
  000003e4  write_tohost    写 0x30000000，ISS 据此停机
    完整列表由 mini_asm.py 在 --map 时按地址排序打印，见 asm.labels。

---- 步骤 3a：ISS 跑 smoke.hex --------------------------------
+ <python> .../iss.py .../smoke.hex

tohost=1 cycles=3 instret=3 irq_seen=0
ISS_PASS
    iss.py main()：先 print() 空行，再打印计数，成功则 ISS_PASS。
    smoke.S 只执行 3 条：lui t0, 0x30000 → addi t1, 1 → sw t1, 0(t0)。
    sw 把 TOHOST 写成 1 后 iss.run() 的 while 条件 tohost==0 不再成立，
    hang 的 jal 不会被执行。没有 MVM，所以 irq_seen=0。

---- 步骤 3b：ISS 跑 e2e_mvm.hex ------------------------------
+ <python> .../iss.py .../e2e_mvm.hex --report .../iss_e2e.json
PASS
    固件 e2e_mvm.S 三组向量都 |y-y_gold|≤1 后，putc('P','A','S','S','\\n')。
    ISS 写 UART_DATA 时 sys.stdout.write 把字符立刻打到终端（无额外换行）。

tohost=1 cycles=5658 instret=5655 irq_seen=3
    tohost=1：固件 write_tohost(1)，与 TOHOST_PASS 相同。
    irq_seen=3：main 调了 3 次 run_one（zeros / fullscale / mixed），
        每次 START 后 handler 进一次 0x10。identity_like 只在黄金 JSON 里，固件没跑。
    cycles - instret = 3：每次 take_irq() 占 1 拍但不算 instret（没执行指令）。
    周期数会随固件改动变化；irq_seen=3 和 tohost=1 是成功判据。
wrote .../reports/iss_e2e.json
ISS_PASS
    --report 把 uart/cycles/events 写成 JSON，供以后对照 RTL 波形。

---- 步骤 4：check_copro_fsm.py --------------------------------
+ <python> .../check_copro_fsm.py
{
  "expected_latency_cycles": 13,
  "mixed": {
    "latency_reg": 13,          settle=8 + adc=4 + 1
    "done_at_cycle": 13,        START 后第 13 拍 DONE=1
    "irq_at_cycle": 13,         同一拍拉 irq（IRQ_EN=1）
    "outpack": 420484641,       即 0x19101621 = pack(33,22,16,25)
    "irq_after_w1c": 0,         写 IRQ=1 后 irq 落下
    "done": 1
  },
  "errors": []                  空列表 = 三组向量全部核对通过
}
COPRO_FSM_PASS  latency=13 cycles @50MHz = 260 ns, W1C ok
    13 * 20 ns = 260 ns。这是题目要填的「访问延迟」，不是 ISS 那几千拍。

---- 步骤 5：check_precision.py --------------------------------
+ <python> .../check_precision.py
directed (int vs ideal real):
  zeros / fullscale     err=0     整数 floor 和实数 round 在端点一致
  mixed                 err=1     8520/252=33.81 → int 33，real round 34
  identity_like         err=1     3969/252=15.75 → int 15，real round 16
    题目允许 ≤ 1 LSB，所以这两行仍算过。

int vs int: n=500 max=0 err0=500 ... PASS
    同一套 mvm_int 自己比自己，必须全 0。
real mismatch=0:  n=500 max=1 ... PASS     量化方式不同，允许差 1
real mismatch=1%: n=500 max=1 ... PASS     1% 电导失配仍 ≤ 1 LSB
real mismatch=5%: n=500 max=2 ... FAIL(>1 LSB exists)
    5% 会冒出 >1 LSB，打印 FAIL 只是这一行的状态。
    总判据 PRECISION_PASS 不把 5% 算进去（见 check_precision.py 的 ok）。
wrote .../reports/precision.json
PRECISION_PASS
"""

# ---- 四个都是标准库模块，不用 pip 安装 ----
# import X          = 把整个模块 X 借来，用的时候写 X.名字
# from X import Y   = 只把 Y 借来，用的时候直接写 Y
import argparse          # 解析命令行开关：--iverilog / --smoke-only
import subprocess        # 另起一个进程跑黄金模型 / 汇编器 / ISS（它们各自也是 .py 模块）
import sys               # sys.executable=正在跑本文件的那个 Python
                         # sys.exit=失败立刻停；sys.platform=区分 Windows / Linux
from pathlib import Path # Path 是「路径」这个类。from pathlib import Path 之后直接写 Path(...)

# __file__ = 解释器注入的「本文件路径」字符串（前后双下划线 = 语言自己用的特殊名）
# Path(__file__)     把字符串变成路径对象。括号里是「传给 Path 构造函数的参数」
# .resolve()         点号 = 调用对象的方法，类似 C++ 的 obj.resolve()
#                    相对路径 → 绝对路径（从 scripts/sim 启动也不会数错）
# .parents[2]        parents 是「所有上级目录」的列表；[2] 和下标用法跟 C 数组一样
#                    往上 3 级：sim → scripts → 仓库根 riscv_mvm_e2e
# 后面所有路径都相对 ROOT，这样无论从哪启动都能找到固件和黄金模型。
ROOT = Path(__file__).resolve().parents[2]


# def 定义函数，相当于 C 的 void run(...)，但：
#   1. 不用写返回类型
#   2. 参数不用写类型
#   3. cwd=None 是「默认参数」：调用 run(cmd) 时没传 cwd，cwd 就是 None
# None 类似 C 的 NULL，表示「没有值」。
def run(cmd, cwd=None):
    """同步执行一条子进程命令，并把命令本身打印出来方便对照日志。

    cmd : 参数列表，不要拼成一整个字符串（避免空格/路径转义问题）。
          例如 ["python", "iss.py", "smoke.hex"]，每一项是一个参数。
    cwd : 工作目录。默认 None，下面会用 cwd or ROOT 填成仓库根。

    子进程失败（非 0）时直接 sys.exit 同一退出码，后面的步骤不会跑。
    不捕获 stdout：黄金模型、汇编器、ISS 的 PASS/FAIL 原文原样冒出来。
    """
    # ------------------------------------------------------------------
    # print("+", " ".join(map(str, cmd)))
    #
    # 从里往外拆，假设 cmd = [Path("iss.py"), "smoke.hex"]：
    #
    # 1) str
    #    内置函数，把任意对象变成字符串。类似 C 的 sprintf。
    #    str(3) → "3"；str(Path("a/b")) → "a/b"
    #
    # 2) map(str, cmd)
    #    对 cmd 里每一项调用 str(...)，得到一个「字符串序列」。
    #    相当于 C 里：
    #        for (i = 0; i < n; i++) tmp[i] = 转成字符串(cmd[i]);
    #    为什么要这一步：cmd 里可能有 Path 对象，join 只收字符串。
    #
    # 3) " ".join(...)
    #    字符串的方法：用空格把一串字符串拼成一句。
    #    " ".join(["python", "iss.py"])  →  "python iss.py"
    #    注意是「分隔符.join(列表)」，不是 join(分隔符, 列表)。
    #
    # 4) print("+", 那句拼好的字)
    #    print 可以收多个参数，默认用空格隔开、末尾换行。
    #    print("+", "python iss.py")  屏幕上就是：  + python iss.py
    #    第一个参数 "+" 是习惯：shell 日志里用 + 表示「接下来要执行这条命令」。
    # ------------------------------------------------------------------
    # flush=True：立刻把这一行挤到终端。否则 stdout 被重定向时（非 TTY），
    # Python 全缓冲，所有 "+ 命令" 会堆到子进程输出之后才一起刷出来。
    print("+", " ".join(map(str, cmd)), flush=True)

    # ------------------------------------------------------------------
    # r = subprocess.run(cmd, cwd=cwd or ROOT)
    #
    # 1) cwd or ROOT
    #    Python 的 or：左边「算真」就取左边，否则取右边。
    #    None、0、""、[] 都算假；其它算真。
    #    所以：
    #        cwd 传了路径 → 用 cwd
    #        cwd 是 None  → 用 ROOT
    #    等价于 C：  cwd != NULL ? cwd : ROOT
    #
    # 2) cwd=...
    #    这是「关键字参数」：按参数名字传，不是按位置。
    #    subprocess.run 的第一个参数是 cmd（位置参数，直接写值），
    #    工作目录那个参数名叫 cwd，必须写成 cwd=某值。
    #    类似 C 里没有的写法；C 只能 run(cmd, ROOT) 按顺序传。
    #
    # 3) subprocess.run(...)
    #    启动一个新进程，等它跑完才返回。
    #    返回值 r 是一个对象，里面有 r.returncode（退出码，0=成功）。
    # ------------------------------------------------------------------
    r = subprocess.run(cmd, cwd=cwd or ROOT)

    # r.returncode 是整数。!= 和 C 一样。
    # 缩进代替了 C 的 { }：if 下面缩进的行才属于 if。
    if r.returncode != 0:
        # sys.exit(n) = 结束本程序，退出码为 n。类似 C 的 exit(n)。
        sys.exit(r.returncode)


def main():
    # argparse.ArgumentParser(...) 构造一个「命令行解析器」对象，赋给 p。
    # description= 又是关键字参数：解析器的说明文字，python run_all.py -h 时会显示。
    p = argparse.ArgumentParser(
        description="黄金向量 → 汇编 hex → ISS（可选 Icarus RTL）",
    )
    # 默认只跑 Python 闭环。加上这个开关才去找 iverilog/vvp，
    # 避免没装 Icarus 的机器连 ISS 都跑不成。
    #
    # p.add_argument(...) 也是关键字参数：
    #   "--iverilog"     位置参数：开关的名字
    #   action="store_true"  出现这个开关时，把对应变量设成 True（否则 False）
    #   help="..."       -h 时显示的帮助
    p.add_argument(
        "--iverilog",
        action="store_true",
        help="ISS 通过后再调 Icarus：单元 MVM + smoke SoC + e2e SoC",
    )
    # 调试汇编器 / CPU 取指时用：跳过 e2e_mvm.S（里面有中断和软件黄金循环）。
    p.add_argument(
        "--smoke-only",
        action="store_true",
        help="只汇编并仿真 fw/asm/smoke.S（写 TOHOST=1 即停）",
    )
    # parse_args() 去读命令行，返回一个对象。
    # 之后用 args.iverilog、args.smoke_only 取值（都是 True/False）。
    args = p.parse_args()

    # 用“正在运行本脚本的那个 Python”，不要写死 python3。
    # Windows 商店版 / venv / py launcher 的可执行文件名都不一样。
    # sys.executable 是字符串，例如 r"C:\Python312\python.exe"
    py = sys.executable

    # ------------------------------------------------------------------
    # 步骤 1：黄金模型
    # 终端接下来（"+ 命令" 之后）会出现：
    #   wrote .../golden/vectors.json
    #     zeros            x=[...] y=[0,0,0,0] acc=[0,0,0,0]
    #     fullscale        ... y=[63,63,63,63] acc=[15876,...]
    #     mixed            ... y=[33,22,16,25] acc=[8520,5720,4260,6390]
    #     identity_like    ... y=[4,8,12,15]   acc=[1008,2016,3024,3969]
    # 数字怎么来的：见本文件顶部对照表，以及 golden/mvm_ref.py 的 mvm_int()。
    # ------------------------------------------------------------------
    # [py, str(...)] 是 list（列表），类似 C 数组，但：
    #   - 用方括号，长度可变
    #   - 元素类型可以混：这里两个都是字符串
    # ROOT / "golden" / "mvm_ref.py"
    #   Path 把 / 重载成「拼接路径」，Windows 上也会变成正确的反斜杠。
    #   结果是一个 Path 对象。
    # str(...) 再把它变成普通字符串，因为 subprocess 要的是字符串列表。
    run([py, str(ROOT / "golden" / "mvm_ref.py")])

    # ------------------------------------------------------------------
    # 步骤 2：汇编
    # mini_asm.py 不依赖 RISC-V GCC，输出 8 KB 的字列表 hex，
    # 给 SRAM 的 $readmemh 和 ISS 的 bytearray 加载器用。
    # ------------------------------------------------------------------
    hexdir = ROOT / "fw" / "hex"
    # mkdir 是 Path 对象的方法（带括号 = 调用）。
    # parents=True    中间目录不存在就一并创建，类似 mkdir -p
    # exist_ok=True   目录已经在也不报错
    # 两个都是关键字参数，True/False 是 Python 的布尔值（C 里是 1/0，但要写成 true/false 那种字）
    hexdir.mkdir(parents=True, exist_ok=True)

    # smoke.S：lui/addi/sw 写 TOHOST，只证明 CPU 能取指、能写 MMIO。
    # 终端：assembled .../smoke.S -> .../smoke.hex  (4 words, last=0xc)
    # 同时写出中间文件（就在 hex 旁边）：
    #   smoke.pass1.txt  pass1 结束：标签/地址 + 仍是文本的指令
    #   smoke.pass2.txt  pass2 结束：已经是 32-bit 机器码
    # 这个 list 跨了好几行，只是为了好读，和写成一行意思完全一样。
    # 每一项都会成为子进程的一个 argv：
    #   argv[0] = python.exe
    #   argv[1] = .../mini_asm.py
    #   argv[2] = .../smoke.S
    #   argv[3] = -o
    #   argv[4] = .../smoke.hex
    run([
        py,
        str(ROOT / "fw" / "python" / "mini_asm.py"),
        str(ROOT / "fw" / "asm" / "smoke.S"),
        "-o",
        str(hexdir / "smoke.hex"),
    ])

    # e2e_mvm.S：写 4x4 向量、开中断、等 IRQ、软件再算一遍黄金值、允许 1 LSB。
    # --map 打印标签地址，方便核对 _start=0x00、irq_handler=0x10。
    # 终端：assembled ... (252 words, last=0x3ec) 然后一列 "  00000000  _start" ...
    run([
        py,
        str(ROOT / "fw" / "python" / "mini_asm.py"),
        str(ROOT / "fw" / "asm" / "e2e_mvm.S"),
        "-o",
        str(hexdir / "e2e_mvm.hex"),
        "--map",
    ])

    # ------------------------------------------------------------------
    # 步骤 3：ISS
    # 行为级 CPU + 与 RTL 同一套 MVM 量化。看到 ISS_PASS 才值得上 Verilog。
    #
    # smoke 终端：
    #     <空行>
    #     tohost=1 cycles=3 instret=3 irq_seen=0
    #     ISS_PASS
    # e2e 终端（固件 UART 先打 PASS，再是 ISS 的计数）：
    #     PASS
    #     tohost=1 cycles=5658 instret=5655 irq_seen=3
    #     wrote .../reports/iss_e2e.json
    #     ISS_PASS
    # 各字段含义见 iss.py main() 和本文件顶部对照表。
    # ------------------------------------------------------------------
    iss = ROOT / "scripts" / "sim" / "iss.py"
    run([py, str(iss), str(hexdir / "smoke.hex")])
    # not 是逻辑非，相当于 C 的 !
    # args.smoke_only 是 True/False。没加 --smoke-only 时是 False，not False → True，走进去。
    if not args.smoke_only:
        run([
            py, str(iss), str(hexdir / "e2e_mvm.hex"),
            "--report", str(ROOT / "reports" / "iss_e2e.json"),
        ])
        # 终端：一段 JSON（latency=13, mixed.outpack=420484641, errors=[]）
        #       然后 COPRO_FSM_PASS  latency=13 cycles @50MHz = 260 ns, W1C ok
        run([py, str(ROOT / "scripts" / "sim" / "check_copro_fsm.py")])
        # 终端：directed 四行 → 四次随机扫描 → wrote precision.json → PRECISION_PASS
        # 注意 real mismatch=5% 那一行会打印 FAIL(>1 LSB exists)，总结果仍是 PASS。
        run([py, str(ROOT / "scripts" / "sim" / "check_precision.py")])

    # ------------------------------------------------------------------
    # 步骤 4（可选）：Icarus RTL
    # Windows 走 PowerShell 包装，Linux/macOS 走 bash。
    # 脚本内部会编 tb_mvm_copro / tb_soc_smoke / tb_soc_e2e。
    # ------------------------------------------------------------------
    if args.iverilog:
        # startswith("win") 是字符串方法：开头是不是 "win"。
        # sys.platform 在 Windows 上是 "win32"，所以为真。
        if sys.platform.startswith("win"):
            ps = ROOT / "scripts" / "sim" / "run_iverilog.ps1"
            run(["powershell", "-File", str(ps)])
        else:
            sh = ROOT / "scripts" / "sim" / "run_iverilog.sh"
            run(["bash", str(sh)])


# 直接 python run_all.py 时 __name__ 是 "__main__"，才调用 main()。
# 被别人 import run_all 时不会自动把整条流水线跑起来。
# == 比较两个字符串，和 C 的 strcmp 不同：Python 的 == 可以直接比字符串内容。
if __name__ == "__main__":
    main()  # 无参调用，括号不能省（省了只是「提到这个函数」不会执行）
