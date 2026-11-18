#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-A 单屏面板（手机一屏无滚动）
用法：python3 ta_panel.py           # 打印面板并覆盖写 panel.txt
刷新：watch -n 60 cat panel.txt      （Mac 上保持一个窗口常看）
纯标准库，Python 3.9 兼容。
"""
import csv, os, sys, datetime

LEDGER = "data_live/tA_ledger.csv"
STATE = "data_live/state.json"
PANEL = "panel.txt"
N = 6
# 显示顺序：默认倒序（最新在上）；python3 ta_panel.py asc 切正序
ORDER = "desc"


def main():
    global ORDER
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("asc", "desc"):
        ORDER = sys.argv[1].lower()
    if not os.path.exists(LEDGER):
        print("台账不存在，先跑 tA_ledger.py")
        return
    rows = [r for r in csv.reader(open(LEDGER, encoding="utf-8")) if len(r) >= 9]
    if rows and rows[0][0] == "台账ID":
        rows = rows[1:]
    if not rows:
        print("台账为空")
        return
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")
    day = [r for r in rows if r[1].startswith(today)] or rows
    last = rows[-1]
    sig_today = [r for r in day if float(r[4]) >= 2.0]

    L = []
    a = L.append
    a("┌──────── T-A 面板 ────────┐")
    a(f" 更新 {datetime.datetime.utcnow() + datetime.timedelta(hours=8):%m-%d %H:%M}  UTC+8")
    a(f" 今日 {len(day)} 根  信号 {len(sig_today)} 次")
    a("├──────────────────────────┤")
    a(f" 最新 {last[0]}  {last[1][-5:]}")
    a(f" 收盘 {float(last[2]):,.2f}   笔数 {last[3]}")
    a(f" z={last[4]}  {last[5]}")
    a(f" 倍数 {last[6]}  振幅基准 {last[7]}%")
    a(f" 结构 {last[8]}")
    a("├──────────────────────────┤")
    a(f" 近 6 根（{'倒序 最新在上' if ORDER == 'desc' else '正序 最新在下'}）")
    for r in (list(reversed(rows[-N:])) if ORDER == "desc" else rows[-N:]):
        a(f" {r[1][-5:]}  {r[4]:>6}  {r[5]:<8} {r[8]}")
    a("├──────────────────────────┤")
    a(" 方向 ⬜ 无信息（仅结构记录）")
    a(" 纪律 不偷看未来 · 幂等不回改")
    a("└──────────────────────────┘")

    txt = "\n".join(L)
    print(txt)
    open(PANEL, "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
