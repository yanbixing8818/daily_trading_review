#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from core.trade_time import is_trade_date



# 使用该函数，可以指定在交易日指定时间执行任务。
# 例如：
# 单次任务（16:00触发）：
#       schedule_trade_day_jobs(main, [(16, 0)])
#
# 多次任务（9:25, 10:00, 11:00, 13:00, 14:00, 15:00触发）：
#       times = [(9, 25), (10, 0), (11, 0), (13, 0), (14, 0), (15, 0)]
#       schedule_trade_day_jobs(hongpanjiashu, times)
 
def schedule_trade_day_jobs(job_func, times, timezone="Asia/Shanghai"):
    """
    交易日指定多个时间点执行job_func
    :param job_func: 需要执行的函数
    :param times: [(hour, minute), ...]
    :param timezone: 时区，默认Asia/Shanghai
    """
    scheduler = BlockingScheduler(timezone=timezone)
    def job_if_trade_day():
        if is_trade_date(datetime.now().date()):
            job_func()
        else:
            print(f"{datetime.now().strftime('%Y-%m-%d')} 非交易日，不执行任务。")
    for hour, minute in times:
        scheduler.add_job(job_if_trade_day, 'cron', hour=hour, minute=minute)
        print(f"定时任务已启动，等待交易日{hour:02d}:{minute:02d}触发...")
    scheduler.start()

