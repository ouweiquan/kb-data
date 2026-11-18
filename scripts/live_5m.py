#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5 分钟级实时预警（双源自动切换）。
源优先级：api.binance.com（直连，最快） → data-api.binance.vision（官方镜像，兜底）
纪律：只用已收盘 K 线（末根丢弃）；窗口取过去 2000 根。
"""
import datetime, json, os, subprocess, sys, time, urllib.request

# --proxy http://127.0.0.1:7890 时，本次运行临时走代理（不写死任何配置）
if "--proxy" in sys.argv:
    i = sys.argv.index("--proxy")
    if i + 1 < len(sys.argv):
        os.environ["HTTPS_PROXY"] = os.environ["HTTP_PROXY"] = sys.argv[i + 1]

BASE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(BASE, "data_live")
STATE = os.path.join(BASE, ".source_cache")
os.makedirs(LIVE, exist_ok=True)

SOURCES = {
    "direct": "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=200",
    "mirror": "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=200",
}
LABEL = {"direct": "直连 api.binance.com", "mirror": "镜像 data-api.binance.vision"}


def try_fetch(key, timeout=5):
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(SOURCES[key], timeout=timeout).read()
        data = json.loads(raw)
        if not data:
            raise ValueError("空响应")
        return data, time.time() - t0, None
    except Exception as ex:
        return None, time.time() - t0, f"{type(ex).__name__}: {ex}"


def get_klines():
    """按 缓存中的赢家 → 其余 顺序尝试，成功即记住"""
    cached = None
    if os.path.exists(STATE):
        cached = open(STATE).read().strip() or None
    order = ([cached] if cached in SOURCES else []) + [k for k in ("direct", "mirror") if k != cached]
    errs = []
    for k in order:
        data, dt, err = try_fetch(k)
        if data:
            with open(STATE, "w") as f:
                f.write(k)
            print(f"数据源：{LABEL[k]}  耗时 {dt:.2f}s" + (f"  （已跳过 {len(errs)} 个不可用源）" if errs else ""))
            for e in errs:
                print(f"  ✗ {e}")
            return data
        errs.append(f"{LABEL[k]} → {err}")
    raise SystemExit("❌ 两个数据源都不可用：\n  " + "\n  ".join(errs))


def save(kl):
    for row in kl:
        t = int(row[0])
        d = datetime.datetime.fromtimestamp(t / 1000)
        fp = os.path.join(LIVE, f"BTCUSDT-5m-{d:%Y-%m-%d}.csv")
        key = str(t)
        if os.path.exists(fp):
            have = {ln.split(",")[0] for ln in open(fp, encoding="utf-8") if ln and ln[0].isdigit()}
            if key in have:
                continue
            with open(fp, "a", encoding="utf-8") as f:
                f.write(",".join(str(x) for x in row) + "\n")
        else:
            with open(fp, "w") as f:
                f.write(",".join(str(x) for x in row) + "\n")


kl = get_klines()
now = datetime.datetime.now()

# 严格只留已收盘 K：开盘时间 + 5 分钟 <= 现在 才算收盘
def _closed(row):
    t = datetime.datetime.fromtimestamp(int(row[0]) / 1000)
    return now >= t + datetime.timedelta(minutes=5)

kl_closed = [r for r in kl if _closed(r)]
dropped = len(kl) - len(kl_closed)
last = kl_closed[-1]
last_t = datetime.datetime.fromtimestamp(int(last[0]) / 1000)
closed_at = last_t + datetime.timedelta(minutes=5)
lag = (now - closed_at).total_seconds() / 60
print(f"抓到 {len(kl)} 根（已收盘 {len(kl_closed)} 根，丢弃未收盘 {dropped} 根）；"
      f"最新已收盘开盘 {last_t:%Y-%m-%d %H:%M}（{closed_at:%H:%M} 收盘），距现在 {lag:.1f} 分钟")
if lag > 10:
    print(f"⚠️ 滞后 {lag:.0f} 分钟偏大：可能数据未推送或网络异常，本次仍按已知数据计算")
save(kl_closed)
print()
subprocess.run([sys.executable, os.path.join(BASE, "vol_warn.py")])

# 单一契约：把这一轮结论写成 state.json（两端唯一的交接物）
STATE_JSON = os.path.join(LIVE, "state.json")
try:
    rec = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "bar_close": last_t.strftime("%Y-%m-%d %H:%M"),
           "close": float(last[4]), "count": int(last[8]),
           "source": open(STATE).read().strip(), "lag_min": round(lag, 1)}
    json.dump(rec, open(STATE_JSON, "w"), ensure_ascii=False, indent=1)
except Exception as ex:
    print(f"（state.json 写入失败：{ex}）")
