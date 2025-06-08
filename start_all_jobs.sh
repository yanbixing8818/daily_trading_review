#!/bin/bash

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 启动各个 Python 脚本（后台运行，互不影响）
nohup python3 daily_basic_data_job.py > daily_basic_data_job.log 2>&1 &
nohup python3 dingtalk_daily_trading_review.py > dingtalk_daily_trading_review.log 2>&1 &
nohup python3 rtime_trading_job.py > rtime_trading_job.log 2>&1 &

echo "所有任务已启动，日志分别写入对应的 .log 文件。" 