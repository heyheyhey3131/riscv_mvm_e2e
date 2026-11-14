#!/usr/bin/env python3
# 上面这一行叫 shebang：在 Linux 上可以直接 ./mvm_ref.py 跑。
# Windows 会忽略它，用你装的那个 python.exe。

"""4x4 模拟 MVM 的数字黄金模型。

本文件是一个 Python 模块（= 一个 .py 文件）。
被直接运行时算测试向量；被 iss.py / check_precision.py import 时只当函数库用。

物理图像（电流型点积）：
    I_j = sum_i V_i * G_ij
数字编码：
    x_i, w_ij ∈ [0, 63]     6-bit
    acc_j     = sum_i x_i * w_ij          ∈ [0, 15876]
    y_j       = acc_j // 252              ∈ [0, 63]
因为 4*63*63 = 15876，15876/63 = 252，满量程恰好映射到 63。

题目指标：MVM 结果误差 ≤ 1 LSB。理想数字模型误差为 0；
带 mismatch 的实数模型会引入量化邻级误差，测试向量保证 ≤ 1 LSB。
"""

# ---- 导入：每个 import 把另一个模块（.py 文件或标准库）借进来 ----
import argparse          # 解析命令行，比如 --mismatch 0.01
import json              # 把 Python 的 list/dict 写成 vectors.json 文本
import sys               # sys.path = Python 找模块的目录列表
from pathlib import Path # 只把 Path 这个类借来。后面直接写 Path(...)，不用 pathlib.Path(...)

# __file__ = 「本文件自己的路径」这个字符串（解释器自动注入，前后双下划线）
# Path(__file__)  括号里的 __file__ 是传给 Path() 的参数
# .resolve()      点号调用方法，得到绝对路径
# .parents[1]     往上 1 级：本文件在 <root>/golden/ → 仓库根
ROOT = Path(__file__).resolve().parents[1]

# sys.path 是一个 list（字符串列表），Python 按这个顺序找模块。
# insert(位置, 值) 是 list 的方法：在下标 0 处插入，原来的元素后移。
# ROOT / "fw" / "python"  用 / 拼路径，得到 Path 对象。
# str(...)                再变成普通字符串，因为 insert 要的是 str。
sys.path.insert(0, str(ROOT / "fw" / "python"))
from socmap import MVM_MAX, MVM_N, MVM_SCALE  # noqa: E402
# noqa: E402 = 告诉检查工具「我知道 import 没写在文件最顶上，这是故意的」

# VECTORS 是一个 list（方括号 = C 里的数组，但长度可变、元素可混类型）。
# 里面每个元素是 dict（花括号 = 键值对，类似 C 结构体，但字段名是字符串）。
# 读字段：v["x"]  类似 C 的 v.x，但键要用方括号和引号。
#
# 直接 python golden/mvm_ref.py（或经由 run_all.py）时，main() 会把每组的
# name / x / y / acc 打到终端。y、acc 不是写在这里的，而是 annotate() 用
# mvm_int() 算出来的：acc_j = Σ_i x[i]*w[i][j]，y_j = acc_j // 252。
VECTORS = [
    {
        "name": "zeros",
        "x": [0, 0, 0, 0],
        "w": [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
        # 终端：  zeros            x=[0, 0, 0, 0] y=[0, 0, 0, 0] acc=[0, 0, 0, 0]
    },
    {
        "name": "fullscale",
        "x": [63, 63, 63, 63],
        "w": [[63, 63, 63, 63], [63, 63, 63, 63], [63, 63, 63, 63], [63, 63, 63, 63]],
        # 终端：  fullscale        ... y=[63, 63, 63, 63] acc=[15876, 15876, 15876, 15876]
        # 4*63*63 = 15876，15876 // 252 = 63（满码进、满码出）
    },
    {
        "name": "mixed",
        "x": [40, 50, 60, 63],
        "w": [
            [40, 10, 20, 30],  # 行 i=输入，列 j=输出。w[i][j] 乘到 y_j 上
            [40, 20, 20, 30],
            [40, 30, 20, 30],
            [40, 40, 20, 30],
        ],
        # 终端：  mixed            ... y=[33, 22, 16, 25] acc=[8520, 5720, 4260, 6390]
        # acc0 = 40*40 + 50*40 + 60*40 + 63*40 = 8520  → 8520//252 = 33
        # acc1 = 40*10 + 50*20 + 60*30 + 63*40 = 5720  → 22
        # acc2 = 40*20 + 50*20 + 60*20 + 63*20 = 4260  → 16
        # acc3 = 40*30 + 50*30 + 60*30 + 63*30 = 6390  → 25
        # 固件 e2e_mvm.S 第三组、check_copro_fsm.py 的 mixed 都用这一组。
    },
    {
        "name": "identity_like",
        "x": [16, 32, 48, 63],
        "w": [
            [63, 0, 0, 0],
            [0, 63, 0, 0],
            [0, 0, 63, 0],
            [0, 0, 0, 63],
        ],
        # 终端：  identity_like    ... y=[4, 8, 12, 15] acc=[1008, 2016, 3024, 3969]
        # 对角 63：16*63=1008//252=4，32*63=2016//252=8，48*63=3024//252=12
        # 63*63=3969//252=15（15.75 向 0 取整；实数模型 round 会得到 16，见 check_precision）
        # 注意：e2e 固件只跑前三组，不跑这一组。
    },
]


# def 定义函数。相当于 C 的 int clamp6(int v)，但：
#   v: int -> int  只是注解（给人看），运行时不检查，可以删掉不影响跑。
#   没有大括号，靠缩进表示函数体。
def clamp6(v: int) -> int:
    """把整数夹到 0..63，对应 6-bit 饱和。"""
    if v < 0:
        return 0
    if v > MVM_MAX:
        return MVM_MAX
    return v


def mvm_int(x, w):
    """纯整数黄金结果，与 RTL mvm_array_digital、ISS、固件 gold_pack 完全一致。

    x: 长度 4 的 list；w: 4x4 的 list 套 list，w[i][j] 是输入 i 到输出 j 的权重。
    Python 的 // 是向 0 取整的整数除法（对非负数），和 Verilog 的 / 一致。
    C 里整数 / 也是向 0 取整，这里和 C 的 acc / 252 相同。

    run_all 步骤 1 终端里的 y= / acc= 就是这里算的。例如 mixed：
        acc=[8520, 5720, 4260, 6390]，y=[33, 22, 16, 25]（acc_j // 252）。
    """
    y = []      # 空列表，后面用 append 往里加。类似 C 里先声明再 y[n++] = ...
    accs = []
    # for j in range(MVM_N):
    #   range(4) 产生 0,1,2,3。j 依次等于这些值。
    #   相当于 C: for (j = 0; j < MVM_N; j++)
    for j in range(MVM_N):
        acc = 0
        for i in range(MVM_N):
            # int(x[i]) 把元素转成整数（万一是别的类型）。类似 C 的 (int)x[i]
            acc += int(x[i]) * int(w[i][j])
        accs.append(acc)            # list.append(值) = 往末尾加一项，没有 C 那种 y[len++]
        y.append(clamp6(acc // MVM_SCALE))
    # return a, b 一次返回两个值。调用方写 y, acc = mvm_int(...)
    # C 做不到这样，得用指针或结构体。Python 其实是打包成一个元组再解开。
    return y, accs


# mismatch=0.0, vref=0.6, g_unit=1e-6 都是默认参数。
# 调用 mvm_real(x, w) 时后三个自动用默认值。
# 1e-6 是科学计数法，等于 0.000001，和 C 一样。
def mvm_real(x, w, mismatch=0.0, vref=0.6, g_unit=1e-6):
    """带电导失配的实数模型，再按同样满量程量化成 6-bit。

    V_i = (x_i/63) * vref
    G_ij = (w_ij) * g_unit * (1 + mismatch_ij)
    I_j  = sum V_i G_ij
    I_fs = 4 * vref * 63 * g_unit   (全部满码、无失配)
    code = round(I_j / I_fs * 63)
    """
    import random                   # 局部 import：只有走进这个函数才加载

    y = []
    iout = []
    # float(x) 转成浮点数，类似 C 的 (double)x。否则全是 int，除法会出问题。
    i_fs = float(MVM_N) * vref * float(MVM_MAX) * g_unit
    for j in range(MVM_N):
        i_j = 0.0
        for i in range(MVM_N):
            # A if 条件 else B   三元表达式，相当于 C 的  条件 ? A : B
            vin = (float(x[i]) / MVM_MAX) * vref if MVM_MAX else 0.0
            g = float(w[i][j]) * g_unit
            # if mismatch:  数字 0.0 算「假」，非 0 算「真」。相当于 if (mismatch != 0)
            if mismatch:
                # random.uniform(a, b) 返回 [a, b] 里的随机浮点数。
                g *= 1.0 + random.uniform(-mismatch, mismatch)
            i_j += vin * g
        iout.append(i_j)
        if i_fs <= 0:
            code = 0
        else:
            # round(x) 四舍五入到整数（返回仍是 float 或 int）；再 int(...) 保证是 int
            code = int(round(i_j / i_fs * MVM_MAX))
        y.append(clamp6(code))
    return y, iout


def annotate(vectors):
    """给每组向量补上 y / acc 两个键，写出 JSON 给后面对照。"""
    out = []
    # for v in vectors:  直接遍历列表里的每个元素，不用写下标。
    # 相当于 C: for (i=0;i<n;i++) { v = vectors[i]; ... }
    for v in vectors:
        y, acc = mvm_int(v["x"], v["w"])
        item = dict(v)              # 拷贝一份 dict，避免改到原来的 VECTORS
        item["acc"] = acc           # 新加一个键，类似 C 结构体多赋一个字段
        item["y"] = y
        out.append(item)
    return out


def main():
    # description= 是关键字参数：按名字传给 ArgumentParser，不是按位置。
    parser = argparse.ArgumentParser(description="MVM golden reference")
    # type=Path   命令行读到的字符串会先交给 Path(...) 再存
    # default=    没写 --write-json 时用这个路径
    # Path(__file__).with_name("vectors.json")  同一目录、只换文件名
    parser.add_argument("--write-json", type=Path, default=Path(__file__).with_name("vectors.json"))
    parser.add_argument("--mismatch", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()      # 真正去读命令行，结果放进 args

    data = annotate(VECTORS)
    # json.dumps(data, indent=2)
    #   位置参数 data：要转换的对象
    #   关键字参数 indent=2：每层缩进 2 个空格，方便人读
    #   返回一个字符串（JSON 文本）
    # args.write_json 是 Path 对象；.write_text(内容, encoding="utf-8") 把字符串写入文件
    args.write_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # f"..." 是 f-string：字符串前加 f，花括号里的表达式会被算出来嵌进去。
    # 相当于 C 的 printf("wrote %s\n", 路径);
    #
    # 终端第 1 行（run_all 步骤 1）：
    #   wrote D:\...\riscv_mvm_e2e\golden\vectors.json
    print(f"wrote {args.write_json}")
    for v in data:
        # {v['name']:16s}  先取值，再按「字符串、宽 16」格式化（左对齐补空格）
        # 字典键用单引号，因为外面 f-string 已经用了双引号
        #
        # 终端接下来 4 行，每组向量一行，例如：
        #   mixed            x=[40, 50, 60, 63] y=[33, 22, 16, 25] acc=[8520, 5720, 4260, 6390]
        # y / acc 来自上面 annotate() → mvm_int()，不是 VECTORS 里手写的。
        print(f"  {v['name']:16s} x={v['x']} y={v['y']} acc={v['acc']}")

    if args.mismatch:
        import random

        random.seed(args.seed)      # 设随机种子，同样的 seed 得到同样的随机数
        # :.2%  把 0.01 格式化成 1.00%
        print(f"\nmismatch ±{args.mismatch:.2%} vs integer golden:")
        for v in data:
            # mismatch=args.mismatch  按名字把第四个参数传进去（前两个按位置）
            # y_r, _ = ...   只要第一个返回值；_ 是约定「这个我不用」
            y_r, _ = mvm_real(v["x"], v["w"], mismatch=args.mismatch)
            # zip(y_r, v["y"])  把两个列表一对一对拿出来：(y_r[0], y[0]), (y_r[1], y[1]), ...
            # [abs(a-b) for a, b in zip(...)]  列表推导：对每一对算绝对值，得到新列表
            # 等价于 C:
            #   for (k=0;k<4;k++) err[k] = abs(y_r[k] - y[k]);
            err = [abs(a - b) for a, b in zip(y_r, v["y"])]
            # max(err)  返回列表里最大的那个数
            print(f"  {v['name']:16s} real={y_r} err={err} max={max(err)}")


# 直接 python mvm_ref.py 时 __name__ 是 "__main__"，才调用 main()。
# 被别人 import 时 __name__ 是 "mvm_ref"，不会自动跑，只把函数借出去。
if __name__ == "__main__":
    main()
