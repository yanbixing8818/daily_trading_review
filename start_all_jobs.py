#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

# 获取当前脚本所在目录，确保子进程在同一目录下启动
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

scripts = [
    'daily_basic_data_job.py',
    'dingtalk_daily_trading_review.py',
    'rtime_trading_job.py',
]

processes = []
for script in scripts:
    script_path = os.path.join(BASE_DIR, script)
    if os.path.exists(script_path):
        print(f"启动: {script}")
        # 使用独立进程启动，且不阻塞主进程
        p = subprocess.Popen([sys.executable, script_path])
        processes.append(p)
    else:
        print(f"未找到脚本: {script}")

print("所有任务已启动。按Ctrl+C可终止本脚本，但子进程需单独关闭。")

# 可选：等待所有子进程结束（如需主控）
# for p in processes:
#     p.wait() 