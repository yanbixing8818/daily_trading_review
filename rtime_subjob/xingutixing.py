from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
from datetime import datetime, timedelta
from chinese_calendar import is_workday
from core.utils import schedule_trade_day_jobs
import pandas as pd
from core.singleton_trade_date import stock_trade_date

# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=0658b0d8ab22e663316d48031e4049fdc20db6d4a15fe4bd23c106ff69ca0103"
KEYWORD = "新股上市提醒"  # 钉钉机器人的关键词

def get_new_stocks_today(date=None):
    """获取指定日期（默认为今日）上市的新股列表"""
    try:
        # 获取日期
        if date is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        else:
            date_str = str(date)
        # print(date_str)
        
        # 使用pywencai查询指定日期上市的新股
        query = f"{date_str}上市的股票"
        print(query)
        df = pywencai.get(query=query, sort_key='上市日期', sort_order='asc')
        
        if df.empty:
            print(f"{date_str}没有新股上市")
            return None
            
        # 检查DataFrame包含哪些列
        available_columns = df.columns.tolist()
        print(f"可用列: {available_columns}")
        
        # 定义需要的列及其备选名称
        required_columns = {
            '股票代码': ['股票代码', '代码'],
            '股票简称': ['股票简称', '名称'],
            '行业': ['行业', '所属行业'],
            '发行价': ['发行价', '价格'],
            '发行市盈率': ['发行市盈率', 'PE']
        }
        
        selected_columns = {}
        
        # 动态选择可用列
        for target_col, alternatives in required_columns.items():
            found = False
            for alt_col in alternatives:
                if alt_col in available_columns:
                    selected_columns[target_col] = alt_col
                    found = True
                    break
            if not found:
                # print(f"警告: 找不到任何与 '{target_col}' 相关的列")
                selected_columns[target_col] = None
        
        # 构建结果DataFrame
        result_data = []
        for _, row in df.iterrows():
            stock_info = {}
            for target_col, source_col in selected_columns.items():
                if source_col:
                    stock_info[target_col] = row.get(source_col, 'N/A')
                else:
                    stock_info[target_col] = 'N/A'
            result_data.append(stock_info)
        
        return pd.DataFrame(result_data) if result_data else None
    except Exception as e:
        print(f"获取新股数据失败: {str(e)}")
        return None

def send_to_dingtalk(content):
    """发送Markdown格式消息到钉钉"""
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": "今日新股上市提醒",
            "text": content + f"\n\n**关键词：{KEYWORD}**"  # 必须包含自定义关键词
        }
    }
    
    # 发送请求
    response = requests.post(DINGTALK_WEBHOOK, json=data, headers=headers)
    
    # 检查响应
    if response.status_code == 200:
        result = response.json()
        if result.get('errcode') == 0:
            print("消息发送成功")
        else:
            print(f"消息发送失败: {result.get('errmsg')}")
    else:
        print(f"请求失败，状态码: {response.status_code}")

def format_stock_data_v2(df, title, show_date_col=False):
    """
    通用新股表格格式化，支持可选上市日期列
    """
    if df is None or df.empty:
        return f"{title}\n无新股上市"
    if show_date_col:
        header = "| 上市日期 | 代码 | 名称 | 行业 | 发行价 | 发行市盈率 |\n"
        sep =   "|----------|------|------|------|--------|------------|\n"
    else:
        header = "| 代码 | 名称 | 行业 | 发行价 | 发行市盈率 |\n"
        sep =   "|------|------|------|--------|------------|\n"
    markdown_content = f"### 🚀 {title}\n" + header + sep
    for _, row in df.iterrows():
        code = row.get('股票代码', 'N/A')
        name = row.get('股票简称', 'N/A')
        industry = row.get('行业', 'N/A')
        price = row.get('发行价', 'N/A')
        pe = row.get('发行市盈率', 'N/A')
        if show_date_col:
            date_ = row.get('上市日期', 'N/A')
            markdown_content += f"| {date_} | {code} | {name} | {industry} | {price} | {pe} |\n"
        else:
            markdown_content += f"| {code} | {name} | {industry} | {price} | {pe} |\n"
    return markdown_content

def send_new_stocks_to_dingtalk(df, title, show_date_col=False):
    content = format_stock_data_v2(df, title, show_date_col)
    send_to_dingtalk(content)

def get_last_n_trade_dates(n=5):
    trade_dates = sorted(stock_trade_date().get_data())
    today = datetime.now().date()
    # 找到今天在交易日历中的索引
    if today in trade_dates:
        idx = trade_dates.index(today)
    else:
        # 如果今天不是交易日，找最近的前一个交易日
        idx = max(i for i, d in enumerate(trade_dates) if d < today)
    # 取前n个交易日（含今天/最近交易日）
    return [trade_dates[idx - i].strftime("%Y-%m-%d") for i in range(n) if idx - i >= 0]

def get_new_stocks_last_n_days(n=5):
    """获取近n个交易日（含今天或最近交易日）新股，返回合并后的DataFrame"""
    all_data = []
    for day in get_last_n_trade_dates(n):
        df = get_new_stocks_today(day)
        if df is not None and not df.empty:
            df.insert(0, '上市日期', day)
            all_data.append(df)
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return None

def notify_new_stocks_all(n_days=5, date=None):
    """
    先推送近n个交易日新股，再推送指定日期新股（如有），两者都推送。
    """
    # 1. 推送近n个交易日新股
    df_n = get_new_stocks_last_n_days(n_days)
    send_new_stocks_to_dingtalk(df_n, f"近{n_days}个交易日新股上市提醒", show_date_col=True)
    # 2. 推送指定日期新股（如有）
    if date is not None:
        df_d = get_new_stocks_today(date)
        send_new_stocks_to_dingtalk(df_d, f"{date}新股上市提醒", show_date_col=False)

def xingutixing_rtime_jobs():
    times = [(9, 10)]
    def job():
        today = datetime.now().date()
        notify_new_stocks_all(5, today)
    schedule_trade_day_jobs(job, times)

if __name__ == "__main__":
    # day = datetime.now().date()
    # notify_new_stocks_all(5, day)  # 查询近5日新股并推送
    # 设置定时任务
    xingutixing_rtime_jobs()