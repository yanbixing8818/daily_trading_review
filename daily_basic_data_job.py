#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import core.stockfetch as stf
from core.trade_time import is_trade_date
from core.stockfetch import fetch_stocks_trade_date

def job():
    now = datetime.datetime.now()
    if is_trade_date(now.date()):
        stf.save_nph_stock_spot_data(now)
        stf.save_nph_etf_spot_data(now)
    else:
        print(f"{now.strftime('%Y-%m-%d')} 非交易日，不执行任务。")

if __name__ == '__main__':
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    # 每周一到周五15:30执行
    scheduler.add_job(job, 'cron', day_of_week='mon-fri', hour=15, minute=30)
    print("调度器已启动，每个交易日15:30自动执行任务（仅A股交易日）。")
    scheduler.start()

