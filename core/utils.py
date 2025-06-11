#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import core.trade_time as tt


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
        if tt.is_trade_date(datetime.now().date()):
            job_func()
        else:
            print(f"{datetime.now().strftime('%Y-%m-%d')} 非交易日，不执行任务。")
    for hour, minute in times:
        scheduler.add_job(job_if_trade_day, 'cron', hour=hour, minute=minute)
        print(f"定时任务已启动，等待交易日{hour:02d}:{minute:02d}触发...")
    scheduler.start()



# 获取指定date日期之前的n个交易日区间，返回(start_date_str, end_date_str)
# 例如：
#       start_date_str, end_date_str = get_recent_trade_range(5)
#       print(start_date_str, end_date_str)

def get_recent_trade_range(date, n=30):
    """
    获取最近n个交易日区间，返回(start_date_str, end_date_str)
    start_date为今天（如非交易日则为最近一个交易日），end_date为start_date往前推n个交易日。
    """
    if not tt.is_trade_date(date):
        end_date = tt.get_previous_trade_date(date)
    else:
        end_date = date
    trade_dates = list(sorted(tt.stock_trade_date().get_data())) 
    idx = trade_dates.index(end_date)
    if idx < n:
        start_date = trade_dates[0]
    else:
        start_date = trade_dates[idx - n + 1]
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    return start_date_str, end_date_str





def test_job():
    print("Job triggered at", datetime.now())
    print("Scheduler started")

if __name__ == "__main__":
    # schedule_trade_day_jobs(test_job, [(10, 21)])
    # date = datetime.now().date()
    date = datetime(2025, 5, 1).date()
    start_date_str, end_date_str = get_recent_trade_range(date, 5)
    print(start_date_str, end_date_str)