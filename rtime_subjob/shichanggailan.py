# import streamlit as st

import os
import pandas as pd
from datetime import datetime
from core.crawling.stock_hist_em import stock_zh_a_spot_em
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from chinese_calendar import is_workday
from core.utils import schedule_trade_day_jobs
from core.database import executeSql, executeSqlFetch

# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=5d1d031097f230cd5d9af236258278e9cc24c5a26826f4eedd8057873c747ba0"
KEYWORD = "整点成交量汇报"  # 钉钉机器人的关键词


def dingtalk_markdown(content, title="A股市场监控提醒", at_mobiles=None, is_at_all=False):
    """
    发送Markdown格式消息到钉钉
    :param content: markdown文本内容
    :param title: 消息标题
    :param at_mobiles: @指定手机号列表（可选）
    :param is_at_all: 是否@所有人（可选）
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content + f"\n\n**关键词：{KEYWORD}**"  # 必须包含自定义关键词
        },
        "at": {
            "atMobiles": at_mobiles or [],
            "isAtAll": is_at_all
        }
    }
    try:
        response = requests.post(DINGTALK_WEBHOOK, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        resp_json = response.json()
        print(f"钉钉消息发送状态: {response.status_code}, 响应: {resp_json}")
        if resp_json.get("errcode", 0) != 0:
            print(f"钉钉消息发送失败: {resp_json}")
    except Exception as e:
        print(f"钉钉消息发送异常: {e}")


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


def ensure_market_overview_table():
    sql = '''
    CREATE TABLE IF NOT EXISTS market_overview (
        date VARCHAR(10) NOT NULL,
        time_str VARCHAR(10) NOT NULL,
        total_amount FLOAT,
        PRIMARY KEY(date, time_str)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    '''
    executeSql(sql)


def save_market_overview(time_str, total_amount):
    ensure_market_overview_table()
    today = datetime.now().strftime('%Y-%m-%d')
    sql = '''REPLACE INTO market_overview (date, time_str, total_amount) VALUES (%s, %s, %s)'''
    executeSql(sql, (today, time_str, total_amount))


def send_market_overview_table_to_dingtalk():
    ensure_market_overview_table()
    columns = ['10:00', '11:00', '13:00', '14:00', '15:00']
    # 查询最近5天日期
    sql_dates = "SELECT DISTINCT date FROM market_overview ORDER BY date DESC LIMIT 5"
    rows = executeSqlFetch(sql_dates)
    if not rows:
        dingtalk_markdown('无市场总成交额数据')
        return
    dates = [r[0] for r in rows]
    # 查询这些日期的所有数据
    sql_data = f"SELECT date, time_str, total_amount FROM market_overview WHERE date IN ({','.join(['%s']*len(dates))})"
    data_rows = executeSqlFetch(sql_data, dates)
    # 组织为 {date: {time_str: total_amount}}
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
            if val is not None and val != ' ---- ':
                val = f"{val:.2f}"
            line.append(str(val) if val is not None else ' ---- ')
        lines.append(' | '.join(line))
    msg = '\n'.join(lines)
    dingtalk_markdown(msg)


def shichanggailan():
    """
    获取市场数据并推送到钉钉，并记录总成交额到表，推送近5日表格
    """
    # 仅在交易日执行
    if not is_workday(datetime.now()):
        print("非交易日，不执行推送。")
        return
    now_str = datetime.now().strftime('%H:%M').lstrip('0')
    stock_zh_a_spot_em_df = stock_zh_a_spot_em()
    overview = calculate_market_overview(stock_zh_a_spot_em_df)
    total_amount = overview.get('总成交额(亿)', 0)
    save_market_overview(now_str, total_amount)
    markdown_content = f"### 🕘 {now_str} A股市场快报\n"
    for k, v in overview.items():
        markdown_content += f"- {k}: {v}\n"
    dingtalk_markdown(markdown_content)
    send_market_overview_table_to_dingtalk()


def shichanggailan_rtime_jobs():
    print("市场概览任务已启动，交易日10:00, 11:00, 13:00, 14:00, 15:00触发，等待触发...")
    times = [(10, 0), (11, 0), (13, 0), (14, 0), (15, 0)]
    schedule_trade_day_jobs(shichanggailan, times)


if __name__ == "__main__":
    shichanggailan_rtime_jobs()
    # shichanggailan()



