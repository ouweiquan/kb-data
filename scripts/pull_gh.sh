#!/bin/bash
# 从公开仓 kb-data 拉取 rolling 文件，喂给台账（Mac 侧一条命令）
set -e
cd "$(dirname "$0")"
URL="https://raw.githubusercontent.com/ouweiquan/kb-data/main/gh_data/BTCUSDT-5m-recent.csv"
mkdir -p data_live
echo "拉取 $URL"
curl -sL --max-time 60 "$URL" -o data_live/gh_recent.csv
LINES=$(wc -l < data_live/gh_recent.csv | tr -d ' ')
echo "gh_recent.csv 行数：$LINES"
if [ "$LINES" -lt 50 ]; then
  echo "行数过少，GitHub 侧可能还没跑出数据，先不喂台账"
  exit 1
fi
python3 tA_ledger.py
python3 ta_panel.py
echo "完成：台账已用 GitHub 补采数据补齐"
