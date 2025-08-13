from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
import pandas as pd
from datetime import datetime
from datetime import timedelta
from core.trade_time import is_trade_date
import re
import os
import random
import time

JINGJIA_BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jingjia_base_data')
os.makedirs(JINGJIA_BASE_DATA_DIR, exist_ok=True)

def get_date_range(start_date, end_date):
    """生成[start_date, end_date]之间所有日期的列表，格式'2025年07月25日'，并返回(datetime.date对象, 中文日期字符串)元组列表"""
    dates = []
    dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    while dt <= end_dt:
        dates.append((dt.date(), dt.strftime("%Y年%m月%d日")))
        dt += timedelta(days=1)
    return dates

if __name__ == "__main__":
    # 设定开始和结束日期
    start_date = "2025-04-07"
    end_date = "2025-08-13"
    all_dates = get_date_range(start_date, end_date)
    for date_obj, trade_date in all_dates:
        # 用trade_time.py的is_trade_date判断
        if not is_trade_date(date_obj):
            print(f"{trade_date} 非交易日，跳过。")
            continue
        date_str = trade_date.replace("年", "").replace("月", "").replace("日", "")
        query = f"创业板,非st,{trade_date}竞价涨幅,{trade_date}竞价匹配价,竞价成交量,{trade_date}05:25分时换手率,{trade_date}05:25分时量比,{trade_date}竞价量，竞价金额, {trade_date}竞价未匹配量,{trade_date}竞价未匹配金额,竞价主力资金流向,{trade_date}流通市值竞价dde大单净额,竞价大单净额,竞价小单净额"
        data = pywencai.get(query=query, loop=True)
        
        # 保存结果
        if isinstance(data, pd.DataFrame) and not data.empty:
            # 去掉所有列名中的[YYYYMMDD]
            def remove_date_suffix(col):
                return re.sub(r'\[\d{8}\]', '', col).strip()
            data.columns = [remove_date_suffix(col) for col in data.columns]
            print(f"{trade_date} 获取到{len(data)}条记录，字段包括: {data.columns.tolist()}")
            csv_path = os.path.join(JINGJIA_BASE_DATA_DIR, f"bidding_data_{date_str}.csv")
            data.to_csv(csv_path, index=False, encoding="utf_8_sig")
        else:
            print(f"{trade_date} 未获取到数据，请检查查询语句或Cookie！")
        
        # 查询后随机睡眠2~5秒，防止封IP
        sleep_time = random.uniform(10, 15)
        print(f"查询后休眠 {sleep_time:.2f} 秒...")
        time.sleep(sleep_time)

