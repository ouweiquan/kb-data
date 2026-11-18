#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""波动预警器：笔数密度突变 → 预测下一根振幅倍数。
用法：python3 vol_warn.py            （看最新一根的预警）
      python3 vol_warn.py --scan     （扫全部历史信号，含事后验证）
纪律：阈值窗口只取过去 2000 根；不预测方向；不产生交易。
"""
import csv, os, statistics, sys

W = 2000
BASE = os.path.dirname(os.path.abspath(__file__))
DIRS = ["data", "data_live"]
rows, seen = [], set()
for dname in DIRS:
    dp = os.path.join(BASE, dname)
    if not os.path.isdir(dp):
        continue
    for fn in sorted(f for f in os.listdir(dp) if f.endswith(".csv")):
        for r in csv.reader(open(os.path.join(dp, fn), newline="")):
            if not r or not r[0].isdigit():
                continue
            t = int(r[0])
            t = t // 1000 if t > 10 ** 14 else t
            if t in seen:
                continue
            seen.add(t)
            rows.append({"t": t, "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
                         "c": float(r[4]), "n": float(r[8])})
rows.sort(key=lambda x: x["t"])


def stats_at(i):
    w = rows[i - W:i]
    m = sum(x["n"] for x in w) / W
    sd = (sum((x["n"] - m) ** 2 for x in w) / W) ** 0.5
    lay = statistics.median(x["h"] - x["l"] for x in w)
    z = (rows[i]["n"] - m) / sd if sd > 0 else 0
    return m, sd, lay, z


def advise(z, lay, px):
    """把 z-score 翻成可执行建议"""
    if z >= 3.0:
        return "🟥 极端", 4.0, "仓位 1/4，止损放宽 4 倍，格距拉宽 4 倍"
    if z >= 2.5:
        return "🟥 剧烈", 3.8, "仓位 1/3，止损放宽 3.8 倍"
    if z >= 2.0:
        return "🟥 放大", 3.5, "仓位 1/2，止损放宽 3.5 倍"
    if z >= 1.0:
        return "🟨 偏热", 1.6, "仓位 2/3，止损放宽 1.6 倍"
    if z <= -1.0:
        return "🟩 安静", 0.5, "可正常仓位，格距收窄"
    return "⬜ 常态", 1.0, "正常仓位与格距"


def show(i, tag="最新"):
    m, sd, lay, z = stats_at(i)
    st, mult, act = advise(z, lay, rows[i]["c"])
    import datetime
    t0 = datetime.datetime.fromtimestamp(rows[i]["t"] / 1000)
    exp = lay * mult
    print(f"[{tag}] {t0:%Y-%m-%d %H:%M}  收盘 {rows[i]['c']:.2f}  笔数 {rows[i]['n']:.0f}  "
          f"z={z:+.2f}  {st}")
    print(f"        基线振幅(过去2000根中位) {lay/rows[i]['c']*100:.3f}%  →  "
          f"预计下一根振幅 ≈ {exp/rows[i]['c']*100:.3f}%（{mult:.1f} 倍）")
    print(f"        建议：{act}")


if "--scan" in sys.argv:
    print(f"扫描全部信号（{len(rows)} 根，窗口 {W}）\n")
    acc = 0; tot = 0
    for i in range(W, len(rows) - 1):
        m, sd, lay, z = stats_at(i)
        if z < 2.0:
            continue
        tot += 1
        act_amp = rows[i + 1]["h"] - rows[i + 1]["l"]
        if act_amp >= lay * 1.5:
            acc += 1
    print(f"  z>2 信号 {tot} 次；事后振幅 ≥1.5 倍基线：{acc} 次（命中率 {acc/tot*100:.1f}%）")
    print(f"\n最近 6 次信号：")
    shown = 0
    for i in range(len(rows) - 2, W, -1):
        m, sd, lay, z = stats_at(i)
        if z >= 2.0:
            show(i, "信号"); print()
            shown += 1
            if shown >= 6:
                break
else:
    show(len(rows) - 1)
