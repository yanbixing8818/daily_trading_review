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

def dingtalk_markdown(content, title="A股市场监控提醒", at_mobiles=None, is_at_all=False):
    """发送Markdown格式消息到钉钉
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
    保存指定时间点的红盘家数到本地CSV
    """
    today = datetime.now().strftime('%Y-%m-%d')
    filename = f'up_stocks_{today}.csv'
    columns = ['9:25', '10:00', '11:00', '13:00', '14:00', '15:00']
    if os.path.exists(filename):
        df = pd.read_csv(filename, index_col=0)
    else:
        df = pd.DataFrame(columns=columns)
        df.index.name = '日期'
    if today not in df.index:
        df.loc[today] = [None]*len(columns)
    df.at[today, time_str] = up_count
    df.to_csv(filename)

def hongpanjiashu():
    """
    获取实时数据并推送红盘家数
    """
    now_str = datetime.now().strftime('%H:%M').lstrip('0')
    stock_zh_a_spot_em_df = stock_zh_a_spot_em()
    overview = calculate_market_overview(stock_zh_a_spot_em_df)
    up_count = overview['上涨家数']
    save_up_stocks_count(now_str, up_count)
    print(f"{now_str} 上涨家数: {up_count} 已保存。")
    up_msg = f"### 🕘 {now_str} 红盘家数快报\n- 红盘家数: {up_count}\n\n{KEYWORD}"
    dingtalk_markdown(up_msg)

def schedule_hongpanjiashu_jobs():
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
    print("定时任务已启动，等待触发...")
    scheduler.start()

if __name__ == "__main__":
    schedule_hongpanjiashu_jobs()



