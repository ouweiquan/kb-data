#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-A 台账日报生成器
用法：python3 tA_report.py            # 今天(UTC+8)
      python3 tA_report.py 2026-11-18
输出：屏幕纯文本 + out/tA_<日期>.txt
纯标准库，Python 3.9 兼容。
"""
import csv, os, sys, datetime, collections

LEDGER = "data_live/tA_ledger.csv"
OUTDIR = "out"


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")
    if not os.path.exists(LEDGER):
        print("本轮失败：台账不存在，先跑 tA_ledger.py")
        return
    rows = [r for r in csv.reader(open(LEDGER, encoding="utf-8")) if len(r) >= 9]
    rows = rows[1:] if rows and rows[0][0] == "台账ID" else rows
    day = [r for r in rows if r[1].startswith(d)]
    if not day:
        print(f"{d} 无台账记录")
        return

    closes = [float(r[2]) for r in day]
    zs = [float(r[4]) for r in day]
    amps = [float(r[7]) for r in day]
    tiers = collections.Counter(r[5] for r in day)
    st2 = sum(1 for r in day if "2K升序" in r[8])
    st3 = sum(1 for r in day if "3K谷" in r[8])
    sig = [r for r in day if float(r[4]) >= 2.0]
    quiet = [r for r in day if float(r[4]) <= -1.0]

    chg = (closes[-1] / closes[0] - 1) * 100
    lines = []
    add = lines.append
    add("=" * 46)
    add(f"T-A 逐根台账日报  {d}（UTC+8）")
    add("=" * 46)
    add(f"根数    {len(day)} 根    区间 {day[0][1][-5:]} ~ {day[-1][1][-5:]}")
    add(f"收盘    {closes[-1]:,.2f}   区间涨跌 {chg:+.2f}%")
    add(f"最高    {max(closes):,.2f}   最低 {min(closes):,.2f}")
    add("-" * 46)
    add("【档位分布】")
    for k, v in tiers.most_common():
        add(f"  {k:<10} {v:>4} 根  {v/len(day)*100:>5.1f}%")
    add("-" * 46)
    add("【结构标注】（仅结构，不作多空依据）")
    add(f"  🟩2K升序  {st2} 次")
    add(f"  🟨3K谷    {st3} 次")
    add("-" * 46)
    add(f"【z>=2 放大信号】共 {len(sig)} 次")
    for r in sig[:10]:
        add(f"  {r[0]}  {r[1][-5:]}  z={r[4]}  {r[5]}  {r[6]}")
    if len(sig) > 10:
        add(f"  ...其余 {len(sig)-10} 次见台账")
    add(f"【z<=-1 安静】共 {len(quiet)} 次")
    for r in quiet[:5]:
        add(f"  {r[0]}  {r[1][-5:]}  z={r[4]}  {r[5]}")
    add("-" * 46)
    add("【振幅】")
    add(f"  基线(2000根中位) {amps[-1]:.3f}%")
    add(f"  当日 z 值 最大 {max(zs):+.2f} / 最小 {min(zs):+.2f} / 均值 {sum(zs)/len(zs):+.2f}")
    add("-" * 46)
    add("【结构→下一根 方向实测】（自证，非预测）")
    for tag in ("2K升序", "3K谷"):
        n = up = 0
        for i in range(len(day) - 1):
            if tag in day[i][8]:
                n += 1
                if float(day[i + 1][2]) > float(day[i][2]):
                    up += 1
        if n:
            add(f"  {tag}：{n} 次 → 下一根收涨 {up} 次，胜率 {up/n*100:.1f}%")
        else:
            add(f"  {tag}：0 次")
    add("-" * 46)
    add(f"【方向】⬜ 无信息（5m 胜率 50~51%、位移 7.0bps < 成本 8bps，不作用途）")
    add("=" * 46)

    txt = "\n".join(lines)
    print(txt)
    os.makedirs(OUTDIR, exist_ok=True)
    p = os.path.join(OUTDIR, f"tA_{d}.txt")
    open(p, "w", encoding="utf-8").write(txt + "\n")
    print(f"\n已保存 → {p}")


if __name__ == "__main__":
    main()
