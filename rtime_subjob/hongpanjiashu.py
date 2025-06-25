# import streamlit as st

import os
import pandas as pd
from datetime import datetime
from core.crawling.stock_hist_em import stock_zh_a_spot_em
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from core.utils import schedule_trade_day_jobs
from core.database import executeSql, executeSqlFetch, checkTableIsExist

# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=294d72c5b9bffddcad4e0220070a9df8104e5e8a3f161461bf2839cfd163b471"
KEYWORD = "整点数据汇报"  # 钉钉机器人的关键词

def dingtalk_text(content):
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "text",
        "text": {
            "content": content + f"\n\n关键词：{KEYWORD}"
        }
    }
    response = requests.post(DINGTALK_WEBHOOK, json=data, headers=headers)
    print(f"钉钉消息发送状态: {response.status_code}, 响应: {response.json()}")

# @st.cache_data(ttl=3600, show_spinner=False)
def calculate_market_overview(df):
    """
    计算市场概览数据
    """
    total_stocks = len(df)
    up_stocks = len(df[df['涨跌幅'] > 0])
    down_stocks = len(df[df['涨跌幅'] < 0])
    flat_stocks = total_stocks - up_stocks - down_stocks

    overview = {
        '总成交额(亿)': round(df['成交额'].sum() / 100000000, 2),
        '上涨家数': up_stocks,
        '下跌家数': down_stocks,
        '平盘家数': flat_stocks,
        '涨跌比': round(up_stocks / (down_stocks + 1e-5), 2),  # 防止除以零
        '平均涨跌幅': round(df['涨跌幅'].mean(), 2)
    }
    return overview

def ensure_up_stocks_table():
    sql = '''
    CREATE TABLE IF NOT EXISTS up_stocks_count (
        date VARCHAR(10) NOT NULL,
        time_str VARCHAR(10) NOT NULL,
        up_count INT,
        PRIMARY KEY(date, time_str)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    '''
    executeSql(sql)

def save_up_stocks_count(time_str, up_count):
    """
    保存指定时间点的红盘家数到表 up_stocks_count，每天多行，主键(date, time_str)
    """
    ensure_up_stocks_table()
    today = datetime.now().strftime('%Y-%m-%d')
    # 插入或更新
    sql = '''REPLACE INTO up_stocks_count (date, time_str, up_count) VALUES (%s, %s, %s)'''
    executeSql(sql, (today, time_str, int(up_count) if pd.notnull(up_count) else None))

def send_up_stocks_table_to_dingtalk():
    """
    读取up_stocks_count表最近5天的数据，每天按时间点升序排列，格式化后推送
    """
    ensure_up_stocks_table()
    columns = ['9:25', '10:00', '11:00', '13:00', '14:00', '15:00']
    # 查询最近5天日期
    sql_dates = "SELECT DISTINCT date FROM up_stocks_count ORDER BY date DESC LIMIT 5"
    rows = executeSqlFetch(sql_dates)
    if not rows:
        dingtalk_text('无红盘家数数据')
        return
    dates = [r[0] for r in rows]
    # 查询这些日期的所有数据
    sql_data = f"SELECT date, time_str, up_count FROM up_stocks_count WHERE date IN ({','.join(['%s']*len(dates))})"
    data_rows = executeSqlFetch(sql_data, dates)
    # 组织为 {date: {time_str: up_count}}
    from collections import defaultdict
    table = defaultdict(dict)
    for d, t, c in data_rows:
        table[d][t] = c
    # 格式化输出
    lines = []
    header = ['日期'] + columns
    lines.append(' | '.join(header))
    for date in dates:
        line = [date[5:]]  # MM-DD
        for col in columns:
            val = table[date].get(col, ' ---- ')
            line.append(str(val) if val is not None else ' ---- ')
        lines.append(' | '.join(line))
    msg = '\n'.join(lines)
    dingtalk_text(msg)

def hongpanjiashu():
    """
    获取实时数据并推送红盘家数，并将表前5天以自定义文本格式通过钉钉发送（每行一行，字段用 | 分隔，避免钉钉竖表渲染问题）
    """
    now_str = datetime.now().strftime('%H:%M').lstrip('0')
    stock_zh_a_spot_em_df = stock_zh_a_spot_em()
    overview = calculate_market_overview(stock_zh_a_spot_em_df)
    up_count = overview['上涨家数']
    save_up_stocks_count(now_str, up_count)
    print(f"{now_str} 上涨家数: {up_count} 已保存。")
    # 打印表前5天，并构造自定义文本格式
    send_up_stocks_table_to_dingtalk()

def hongpanjiashu_rtime_jobs():
    print("红盘家数任务已启动, 9:25, 10:00, 11:00, 13:00, 14:00, 15:00, 等待触发...")
    times = [(9, 25), (10, 0), (11, 0), (13, 0), (14, 0), (15, 0)]
    schedule_trade_day_jobs(hongpanjiashu, times)

if __name__ == "__main__":
    hongpanjiashu_rtime_jobs()


