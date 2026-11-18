#!/usr/bin/env python3
# kb-data 境外补采器（公开仓）：抳币安 5m×200 根，写 CSV
# 纯标准库。
# 2026-11-18：GitHub runner 在 US，api.binance.com 对美国 IP 返回 451，
# 改为多源探测：api.binance.com(直连) → data-api.binance.vision(官方数据镜像)。
# 未收盘K一律丢弃（open_time+5min <= now 才算收盘）。
# 跨所价差已移除：US runner 拿不到 fapi/Bybit，且 27 样本 max +1.3bps 已判死。
import glob, json, os, sys, datetime, urllib.request, urllib.error

OUT = "gh_data"
TIMEOUT = 15
RECENT_KEEP = 1500
UA = {"User-Agent": "kblab-gh/1.0"}

KL_SRC = [
    ("direct", "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=200"),
    ("vision", "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=200"),
]


def get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def write_rows(rows):
    os.makedirs(OUT, exist_ok=True)
    added = 0
    for r in rows:
        t = int(r[0])
        d = datetime.datetime.utcfromtimestamp(t / 1000)
        fp = os.path.join(OUT, "BTCUSDT-5m-%s.csv" % d.strftime("%Y-%m-%d"))
        have = set()
        if os.path.exists(fp):
            have = {ln.split(",")[0] for ln in open(fp) if ln and ln[0].isdigit()}
        if str(t) in have:
            continue
        with open(fp, "a") as f:
            f.write(",".join(str(x) for x in r) + "\n")
        added += 1
    return added


def rebuild_recent():
    rows = {}
    for fp in glob.glob(os.path.join(OUT, "BTCUSDT-5m-*.csv")):
        if fp.endswith("recent.csv"):
            continue
        for ln in open(fp):
            ln = ln.strip()
            if not ln or not ln[0].isdigit():
                continue
            rows[ln.split(",")[0]] = ln
    if not rows:
        return 0
    keys = sorted(int(k) for k in rows)[-RECENT_KEEP:]
    with open(os.path.join(OUT, "BTCUSDT-5m-recent.csv"), "w") as f:
        for k in keys:
            f.write(rows[str(k)] + "\n")
    return len(keys)


def _closed(r, nowms):
    return int(r[0]) + 300000 <= nowms


def main():
    ok = 0
    nowms = int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)

    for name, url in KL_SRC:
        try:
            kl = get(url)
            if not kl:
                raise ValueError("空响应")
            n_all = len(kl)
            kl = [r for r in kl if _closed(r, nowms)]   # 未收盘K一律丢弃
            n = write_rows(kl)
            r = rebuild_recent()
            print("[klines:%s] 取 %d 根，丢弃未收盘 %d 根，新增 %d 根；recent=%d 行"
                  % (name, n_all, n_all - len(kl), n, r))
            ok += 1
            break
        except urllib.error.HTTPError as e:
            print("[klines:%s] HTTP %s  %s" % (name, e.code, e.reason))
        except Exception as e:
            print("[klines:%s] 失败 %s: %s" % (name, type(e).__name__, e))

    if ok == 0:
        print("FAILED: K 线通道全部不可用")
        sys.exit(1)
    print("OK: K 线通道成功（1/1）")


if __name__ == "__main__":
    main()
