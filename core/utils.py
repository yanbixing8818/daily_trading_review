#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from core.trade_time import is_trade_date



# 使用该函数，可以指定在交易日指定时间执行任务。
# 例如：schedule_trade_day_job(main, 16, 0)，表示在交易日16:00执行main函数。

def schedule_trade_day_job(job_func, hour, minute, timezone="Asia/Shanghai"):
    """
    交易日指定时间执行job_func
    :param job_func: 需要执行的函数
    :param hour: 小时（24小时制）
    :param minute: 分钟
    :param timezone: 时区，默认Asia/Shanghai
    """
    scheduler = BlockingScheduler(timezone=timezone)
    def job_if_trade_day():
        if is_trade_date(datetime.now().date()):
            job_func()
        else:
            print(f"{datetime.now().strftime('%Y-%m-%d')} 非交易日，不执行任务。")
    scheduler.add_job(job_if_trade_day, 'cron', hour=hour, minute=minute)
    print(f"定时任务已启动，等待交易日{hour:02d}:{minute:02d}触发...")
    scheduler.start()




