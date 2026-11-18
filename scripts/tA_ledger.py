#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-A 逐根台账（逐K记账）
用法：
  python3 tA_ledger.py                # 补齐今天(UTC+8)及以后所有已收盘K
  python3 tA_ledger.py 2026-11-18     # 从指定日期起补齐
  python3 tA_ledger.py --tail 20      # 只打印台账最后20行

纪律：
  - 只用已收盘K（末根若未收盘由 live_5m.py 丢弃；本脚本按"最新一根 open_time+5min <= now"自行再过滤一次）
  - 严格从左到右，z 只用该根之前 2000 根的 count，不偷看未来
  - 幂等：已写入的 bar 不重复写，不覆盖历史判定
纯标准库，Python 3.9 兼容。
"""
import csv, os, sys, statistics, datetime, json

W = 2000                      # 基线窗口
LEDGER = "data_live/tA_ledger.csv"
FIELDS = ["台账ID", "时间戳", "收盘价", "笔数", "z", "档位", "预测倍数",
          "基线振幅%", "结构标注", "备注"]


def ts_ms_to_local_str(ms):
    t = datetime.datetime.utcfromtimestamp(ms / 1000 + 8 * 3600)
    return t.strftime("%Y-%m-%d %H:%M")


def now_ms():
    """真实 UTC 毫秒时间戳"""
    return int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)


def local_str_to_ms(s):
    """台账里的 'YYYY-MM-DD HH:MM'（UTC+8 本地墙钟）→ UTC 毫秒"""
    dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
    return int((dt - datetime.datetime(1970, 1, 1)).total_seconds() * 1000) - 8 * 3600 * 1000


def closed(t_ms):
    """open_time + 5 分钟 <= 现在 才算收盘"""
    return t_ms + 300000 <= now_ms()


def load_bars():
    bars = {}
    for d in ("data", "data_live"):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".csv") or fn in ("cron_ledger.csv", "tA_ledger.csv"):
                continue
            try:
                f = open(os.path.join(d, fn), newline="", encoding="utf-8")
            except Exception:
                continue
            for r in csv.reader(f):
                if len(r) < 9 or not r[0].strip().isdigit():
                    continue
                try:
                    t = int(r[0])
                    if t > 10 ** 14:
                        t //= 1000
                    o, h, l, c, cnt = float(r[1]), float(r[2]), float(r[3]), float(r[4]), int(r[8])
                except Exception:
                    continue
                bars[t] = (o, h, l, c, cnt)
            f.close()
    return bars


def tier(z):
    if z >= 3.0:
        return "🟥放大-极强", "0.25x", "仓位 1/4，格距放大"
    if z >= 2.5:
        return "🟨放大-强", "0.33x", "仓位 1/3，格距放大"
    if z >= 2.0:
        return "🟨放大", "0.50x", "仓位 1/2，格距放大"
    if z >= 1.0:
        return "🟩偏活跃", "0.67x", "仓位 2/3"
    if z <= -1.0:
        return "⬜安静", "0.50x", "仓位 0.5倍，格距收窄"
    return "⬜常态", "1.00x", "正常仓位与格距"


def structure(hist):
    """hist: 截至当前根的 (o,h,l,c,cnt) 列表。只用已见数据。
    2K升序：高点抬高且低点抬高 → 🟩▲
    3K谷：三根下-上-下，中根低点最低，第三根收盘不破中根低点 → 🟨谷
    """
    tags = []
    if len(hist) >= 2:
        p, c = hist[-2], hist[-1]
        if c[1] > p[1] and c[2] > p[2]:
            tags.append("🟩2K升序▲")
    if len(hist) >= 3:
        a, b, c3 = hist[-3], hist[-2], hist[-1]
        if b[2] < a[2] and b[2] < c3[2] and c3[3] > b[2]:
            tags.append("🟨3K谷")
    return "+".join(tags) if tags else "—"


def main():
    since = None
    tail_only = 0
    args = sys.argv[1:]
    if args and args[0] == "--tail":
        tail_only = int(args[1]) if len(args) > 1 else 20
    elif args:
        since = args[0]

    if tail_only:
        if os.path.exists(LEDGER):
            rows = list(csv.reader(open(LEDGER, encoding="utf-8")))
            for r in rows[-tail_only:]:
                print(" | ".join(r))
        return

    if since is None:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        since = now.strftime("%Y-%m-%d")

    bars = load_bars()
    if not bars:
        print("本轮失败：data/ 与 data_live/ 均无可用K线")
        return
    ks = sorted(bars)
    ks = [k for k in ks if closed(k)]   # 未收盘K一律丢弃（防止半根笔数当信号）

    done = set()
    raw_rows = []
    if os.path.exists(LEDGER):
        raw_rows = [r for r in csv.reader(open(LEDGER, encoding="utf-8")) if len(r) >= 2]
    # 剔除队尾未收盘行（只动"最后一行"，不碰任何已收盘的历史判定）
    dropped = 0
    while len(raw_rows) > 0 and raw_rows[-1][0] != "台账ID" and raw_rows[-1][1]:
        try:
            t_ms = local_str_to_ms(raw_rows[-1][1])
        except Exception:
            break
        if closed(t_ms):
            break
        raw_rows.pop()
        dropped += 1
    if dropped:
        with open(LEDGER, "w", newline="", encoding="utf-8") as fw:
            ww = csv.writer(fw)
            for r in raw_rows:
                ww.writerow(r)
        print(f"⚠️ 剔除队尾未收盘行 {dropped} 根（收盘后会重新入账）")
    for r in raw_rows:
        if r[0] != "台账ID":
            done.add(r[1])

    new_file = not os.path.exists(LEDGER)
    f = open(LEDGER, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if new_file:
        w.writerow(FIELDS)
        seq = 0
    else:
        seq = len(done)

    added, skipped = 0, 0
    for i in range(W, len(ks)):
        t = ks[i]
        ts_str = ts_ms_to_local_str(t)
        if ts_str[:10] < since:
            continue
        if ts_str in done:
            skipped += 1
            continue
        win = [bars[k][4] for k in ks[i - W:i]]
        m = sum(win) / W
        sd = statistics.pstdev(win)
        if sd == 0:
            continue
        z = (bars[t][4] - m) / sd
        # 基线振幅（过去2000根 high-low / close 中位）
        amps = sorted((bars[k][1] - bars[k][2]) / bars[k][3] for k in ks[i - W:i])
        base_amp = amps[len(amps) // 2] * 100
        tag, mult, note = tier(z)
        st = structure([bars[k] for k in ks[max(0, i - 2):i + 1]])
        seq += 1
        w.writerow([f"TA{seq:05d}", ts_str, f"{bars[t][3]:.2f}", bars[t][4],
                    f"{z:.2f}", tag, mult, f"{base_amp:.3f}", st, note])
        added += 1
    f.close()

    rows = list(csv.reader(open(LEDGER, encoding="utf-8")))[1:]
    print(f"本轮补齐 {added} 根（已存在跳过 {skipped} 根），台账共 {len(rows)} 行")
    print("最近 5 根：")
    for r in rows[-5:]:
        print(" | ".join(r))
    sig = [r for r in rows if float(r[4]) >= 2.0]
    print(f"台账内 z>=2.0 信号 {len(sig)} 次" + (f"，最近 {sig[-1][0]} {sig[-1][1]} z={sig[-1][4]}" if sig else ""))


if __name__ == "__main__":
    main()
