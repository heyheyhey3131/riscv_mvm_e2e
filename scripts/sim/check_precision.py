#!/usr/bin/env python3
"""精度与失配扫描：对照题目「MVM 结果误差 ≤ 1 LSB」。

本文件是模块，直接跑会写 reports/precision.json。
它 from mvm_ref import ... 把黄金模型当函数库用，自己不再重写公式。

三层：
  1. 整数黄金模型自洽（误差必须为 0）
  2. 无失配实数电流模型 vs 整数黄金（量化方式不同，允许 1 LSB）
  3. 电导失配 Monte Carlo vs 整数黄金
"""

import argparse
import json
import random              # 随机数。Random(seed) 可复现：同样种子 → 同样向量
import sys
from pathlib import Path

# 本文件在 <root>/scripts/sim/ → parents[2] = 仓库根。和 run_all.py 同一套写法。
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "golden"))
sys.path.insert(0, str(ROOT / "fw" / "python"))

from mvm_ref import VECTORS, annotate, mvm_int, mvm_real  # noqa: E402
from socmap import MVM_MAX, MVM_N  # noqa: E402


def max_abs_err(a, b):
    # zip(a, b) 把两个列表一对一对拿出来，类似 C:
    #   for (i = 0; i < n; i++) { x = a[i]; y = b[i]; ... }
    # max(...) 返回里面最大的那个数。
    # (abs(x - y) for x, y in zip(a, b))  是生成器：边走边算，不先建一个列表。
    return max(abs(x - y) for x, y in zip(a, b))


def rand_vec(rng):
    # rng.randint(0, MVM_MAX)  调用 rng 这个对象的方法，返回 [0, 63] 的整数。
    # 点号 = 对象的方法，类似 C++ 的 rng.randint(0, 63)。
    # [表达式 for _ in range(N)]  列表推导，相当于：
    #   x = []; for (i = 0; i < N; i++) x.append(rng.randint(0, MVM_MAX));
    # _ 表示「循环变量我不用」，只想重复 N 次。
    x = [rng.randint(0, MVM_MAX) for _ in range(MVM_N)]
    # 嵌套推导：外层 4 行，内层每行 4 列，得到 4x4。
    w = [[rng.randint(0, MVM_MAX) for _ in range(MVM_N)] for _ in range(MVM_N)]
    return x, w     # 一次返回两个值。调用方： x, w = rand_vec(rng)


# round_mode="int" 是默认参数：调用 scan(n, 0.0, seed) 时第四个参数自动是 "int"
def scan(n, mismatch, seed, round_mode="int"):
    # random.Random(seed)  构造一个独立的随机数发生器对象，赋给 rng。
    # 括号里的 seed 是传给构造函数的参数。同样的 seed → 同样的随机序列。
    rng = random.Random(seed)
    hist = {0: 0, 1: 0, "gt1": 0}  # dict：键可以是 int 也可以是字符串
    worst = 0
    worst_case = None               # None ≈ C 的 NULL，表示「还没有最坏样本」
    for k in range(n):
        x, w = rand_vec(rng)
        y_int, _ = mvm_int(x, w)    # _ 丢掉第二个返回值（acc 这里用不到）
        if mismatch == 0 and round_mode == "int":
            # Python 的 == 可以直接比字符串内容，不用 strcmp
            y_b, _ = mvm_int(x, w)
        else:
            # 2**30 是 2 的 30 次方，C 里是 1<<30 或 pow(2,30)
            rng_m = random.Random(rng.randint(0, 2**30))
            # mvm_real 内部用 random 模块全局 RNG，所以要先备份、再恢复
            old = random.getstate()
            random.seed(rng_m.randint(0, 2**30))
            # mismatch=mismatch  关键字参数：按名字把值传给 mvm_real 的 mismatch
            y_b, _ = mvm_real(x, w, mismatch=mismatch)
            random.setstate(old)
        e = max_abs_err(y_int, y_b)
        worst = max(worst, e)       # max 也可以直接收两个数，返回较大者
        if e > 1:
            hist["gt1"] += 1
            # is None  判断是不是空值，比 == None 更地道（对 None 专门用 is）
            # or  左边为真就不再算右边。这里：还没有记录，或当前误差更大，就更新
            if worst_case is None or e > worst_case[0]:
                # (a, b, c, d, e) 元组：一组绑在一起的值，用下标 [0] [1] ... 取
                # 和 list 很像，但写出来之后不能改（tuple 不可变）
                worst_case = (e, x, w, y_int, y_b)
        else:
            # dict.get(键, 默认)  键不存在时返回默认值，不会报错。
            # 相当于 C:  hist[e] = (hist 里有 e ? hist[e] : 0) + 1
            hist[e] = hist.get(e, 0) + 1
    # return { ... }  返回一个 dict。键是字符串，值类型可以混。
    # "worst": None if 条件 else { ... }
    #   又是三元表达式：条件为真取 None，否则取后面那个 dict
    return {
        "n": n,
        "mismatch": mismatch,
        "max_err_lsb": worst,
        "err0": hist.get(0, 0),
        "err1": hist.get(1, 0),
        "err_gt1": hist["gt1"],
        "pass_le1": hist["gt1"] == 0,
        "worst": None
        if worst_case is None
        else {
            "err": worst_case[0],
            "x": worst_case[1],
            "w": worst_case[2],
            "y_int": worst_case[3],
            "y_real": worst_case[4],
        },
    }


def main():
    p = argparse.ArgumentParser()
    # -n 是短选项。type=int 表示把命令行字符串转成整数再存。
    # default=500 没写 -n 时用 500。
    p.add_argument("-n", type=int, default=500)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("-o", type=Path, default=ROOT / "reports" / "precision.json")
    args = p.parse_args()

    directed = []
    for v in annotate(VECTORS):
        y_r, _ = mvm_real(v["x"], v["w"], mismatch=0.0)
        # append 的参数是一个新 dict，用花括号当场写出来
        directed.append(
            {
                "name": v["name"],
                "x": v["x"],
                "y_int": v["y"],
                "y_real_ideal": y_r,
                "err_lsb": max_abs_err(v["y"], y_r),
            }
        )

    # scan(...) 的第四个参数用 round_mode="int" 按名字传，避免记错顺序
    report = {
        "directed": directed,
        "random_int_vs_int": scan(args.n, 0.0, args.seed, round_mode="int"),
        "random_real_mismatch_0": scan(args.n, 0.0, args.seed, round_mode="real"),
        "random_real_mismatch_1pct": scan(args.n, 0.01, args.seed, round_mode="real"),
        "random_real_mismatch_5pct": scan(args.n, 0.05, args.seed, round_mode="real"),
    }

    # args.o 是 Path；.parent 是它所在目录；.mkdir(...) 创建目录
    # parents=True / exist_ok=True  关键字参数，见 run_all.py 的同样写法
    args.o.parent.mkdir(parents=True, exist_ok=True)
    args.o.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # 终端（run_all 步骤 5）从这里开始。int = mvm_int 的 floor(acc/252)；
    # real = mvm_real 的 round(I/I_fs*63)。端点一致，中间可能差 1 LSB。
    print("directed (int vs ideal real):")
    for d in directed:
        # 实际会打印：
        #   zeros            int=[0, 0, 0, 0]       real=[0, 0, 0, 0]       err=0
        #   fullscale        int=[63, 63, 63, 63]   real=[63, 63, 63, 63]   err=0
        #   mixed            int=[33, 22, 16, 25]   real=[34, 23, 17, 25]   err=1
        #       8520/252=33.81 → floor 33，round 34；5720/252=22.70 → 22 vs 23；
        #       4260/252=16.90 → 16 vs 17；6390/252=25.36 → 两边都是 25。max abs=1
        #   identity_like    int=[4, 8, 12, 15]     real=[4, 8, 12, 16]     err=1
        #       3969/252=15.75 → floor 15，round 16
        print(f"  {d['name']:16s} int={d['y_int']} real={d['y_real_ideal']} err={d['err_lsb']}")

    def show(title, block):
        # 函数里面再定义函数：show 只给 main 用，外面看不见
        # "PASS" if 条件 else "FAIL..."  三元，相当于 C 的  条件 ? "PASS" : "FAIL"
        status = "PASS" if block["pass_le1"] else "FAIL(>1 LSB exists)"
        # 相邻两个 f-string 会自动拼成一个，方便换行写
        #
        # 一行里的字段：
        #   n=500     随机样本数（-n 可改）
        #   max=      这 500 次里最大 |y_int - y_b|
        #   err0/err1 误差刚好 0 / 刚好 1 LSB 的次数
        #   gt1=      误差 >1 的次数；非 0 则本行 FAIL
        print(
            f"{title}: n={block['n']} max={block['max_err_lsb']} "
            f"err0={block['err0']} err1={block['err1']} gt1={block['err_gt1']} {status}"
        )

    # 位置参数：第一个给 title，第二个给 block
    #   int vs int:            同一公式自己比自己，必须 max=0、err0=500、PASS
    #   real mismatch=0:       无失配但 round vs floor，max=1 仍 PASS
    #   real mismatch=1%:      1% 电导失配，题目要求的工作区，应 PASS
    #   real mismatch=5%:      故意打得更重，通常 max=2 且 gt1>0，本行会印 FAIL
    show("int vs int", report["random_int_vs_int"])
    show("real mismatch=0", report["random_real_mismatch_0"])
    show("real mismatch=1%", report["random_real_mismatch_1pct"])
    show("real mismatch=5%", report["random_real_mismatch_5pct"])
    print(f"wrote {args.o}")

    # all(条件 for d in directed)  每一个 d 都满足才为真，相当于一串 &&
    # 注意：5% 那一组故意不进 ok。所以终端可以同时看到
    #   real mismatch=5%: ... FAIL(>1 LSB exists)
    #   PRECISION_PASS
    # 这不是自相矛盾：5% 只是扫描边界，总判据覆盖 directed + 整数自洽 + 0%/1% 失配。
    ok = (
        all(d["err_lsb"] <= 1 for d in directed)
        and report["random_int_vs_int"]["pass_le1"]
        and report["random_real_mismatch_0"]["pass_le1"]
        and report["random_real_mismatch_1pct"]["pass_le1"]
    )
    print("PRECISION_PASS" if ok else "PRECISION_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    # sys.exit(n)  结束进程，退出码为 n。C 的 return n / exit(n)
    # 这里 n 是 main() 的返回值，所以要先调用 main()
    sys.exit(main())
