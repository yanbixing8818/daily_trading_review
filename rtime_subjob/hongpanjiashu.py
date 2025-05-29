# import streamlit as st

import os
import pandas as pd
from datetime import datetime
from core.crawling.stock_hist_em import stock_zh_a_spot_em
import requests
from apscheduler.schedulers.blocking import BlockingScheduler

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

def save_up_stocks_count(time_str, up_count):
    """
    保存指定时间点的红盘家数到同一个CSV文件（up_stocks.csv），每天为一行，最新数据在最上面。
    """
    filename = 'up_stocks.csv'
    columns = ['9:25', '10:00', '11:00', '13:00', '14:00', '15:00']
    today = datetime.now().strftime('%Y-%m-%d')
    if os.path.exists(filename):
        df = pd.read_csv(filename, index_col=0)
    else:
        df = pd.DataFrame(columns=columns)
        df.index.name = '日期'
    if today not in df.index:
        # 新的一天，插入到最前面
        new_row = pd.DataFrame([[None]*len(columns)], columns=columns, index=[today])
        df = pd.concat([new_row, df])
    df.at[today, time_str] = up_count
    df.to_csv(filename)

def send_up_stocks_csv_to_dingtalk():
    """
    读取up_stocks.csv，每行数据用 | 分隔，缺失数据用'----'占位，每行一行，拼成字符串后用dingtalk_text发送，确保钉钉换行。
    """
    try:
        df = pd.read_csv('up_stocks.csv', index_col=0)
        df.index = pd.to_datetime(df.index, errors='coerce', infer_datetime_format=True).strftime('%m-%d')
        lines = []
        header = ['日期'] + list(df.columns)
        lines.append(' | '.join(header))
        for idx, row in df.iterrows():
            line = [str(idx)]
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    val = ' ------ '
                line.append(str(val))
            lines.append(' | '.join(line))
        msg = '\n'.join(lines)
        dingtalk_text(msg)
    except Exception as e:
        print(f"读取up_stocks.csv失败: {e}")


def hongpanjiashu():
    """
    获取实时数据并推送红盘家数，并将csv前5行以自定义文本格式通过钉钉发送（每行一行，字段用 | 分隔，避免钉钉竖表渲染问题）
    """
    now_str = datetime.now().strftime('%H:%M').lstrip('0')
    stock_zh_a_spot_em_df = stock_zh_a_spot_em()
    overview = calculate_market_overview(stock_zh_a_spot_em_df)
    up_count = overview['上涨家数']
    save_up_stocks_count(now_str, up_count)
    print(f"{now_str} 上涨家数: {up_count} 已保存。")
    # 打印csv文件前5行，并构造自定义文本格式
    send_up_stocks_csv_to_dingtalk()


def hongpanjiashu_rtime_jobs():
    """
    启动定时任务，在指定时间点推送红盘家数
    """
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    times = [
        {"hour": 9, "minute": 25},
        {"hour": 10, "minute": 0},
        {"hour": 11, "minute": 0},
        {"hour": 13, "minute": 0},
        {"hour": 14, "minute": 0},
        {"hour": 15, "minute": 0},
    ]
    for t in times:
        scheduler.add_job(hongpanjiashu, 'cron', **t)
    print("红盘家数任务已启动, 9:25, 10:00, 11:00, 13:00, 14:00, 15:00, 等待触发...")
    scheduler.start()


if __name__ == "__main__":
    hongpanjiashu_rtime_jobs()



