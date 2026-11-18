#!/bin/bash
# T-A 每 5 分钟落地脚本（launchd / cron 通用调用）
# 幂等：重复跑不会重复记账
cd "$HOME/kb-lab" || exit 1
PY=/usr/bin/python3

$PY live_5m.py   >> live.log 2>&1
$PY tA_ledger.py >> tA.log   2>&1
$PY ta_panel.py   > panel.txt 2>&1
