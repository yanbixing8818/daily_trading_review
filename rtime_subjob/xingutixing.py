from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
from datetime import datetime, timedelta
from chinese_calendar import is_workday
from core.utils import schedule_trade_day_jobs

# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=0658b0d8ab22e663316d48031e4049fdc20db6d4a15fe4bd23c106ff69ca0103"
KEYWORD = "新股上市提醒"  # 钉钉机器人的关键词

def get_new_stocks_today():
    """获取今日上市的新股列表"""
    try:
        # 获取今天的日期
        # today = datetime.now().strftime("%Y-%m-%d")
        date = datetime(2025, 6, 11).date().strftime("%Y-%m-%d")
        print(date)
        
        # 使用pywencai查询今日上市的新股
        query = f"{date}上市的股票"
        print(query)
        df = pywencai.get(query=query, sort_key='上市日期', sort_order='asc')
        
        if df.empty:
            print(f"今日({date})没有新股上市")
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
                print(f"警告: 找不到任何与 '{target_col}' 相关的列")
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

def format_stock_data(df):
    """将股票数据格式化为Markdown表格"""
    if df is None or df.empty:
        return "今日没有新股上市"
    
    markdown_content = "### 🚀 今日新股上市提醒\n"
    markdown_content += "| 代码 | 名称 | 行业 | 发行价 | 发行市盈率 |\n"
    markdown_content += "|------|------|------|--------|------------|\n"
    
    for _, row in df.iterrows():
        code = row.get('股票代码', 'N/A')
        name = row.get('股票简称', 'N/A')
        industry = row.get('行业', 'N/A')
        price = row.get('发行价', 'N/A')
        pe = row.get('发行市盈率', 'N/A')
        
        markdown_content += f"| {code} | {name} | {industry} | {price} | {pe} |\n"
    
    return markdown_content

def notify_new_stocks():
    """主逻辑：获取新股信息并发送到钉钉"""
    # 检查是否为工作日
    if not is_workday(datetime.now()):
        print("今日非交易日，跳过执行")
        return
    
    # 获取新股数据
    new_stocks = get_new_stocks_today()
    
    # 格式化数据并发送到钉钉
    markdown_content = format_stock_data(new_stocks)
    send_to_dingtalk(markdown_content)

def schedule_daily_job():
    """设置每日定时任务"""
    scheduler = BlockingScheduler()
    
    # 设置在每个工作日的9:00执行任务
    scheduler.add_job(
        notify_new_stocks,
        CronTrigger(
            day_of_week='mon-fri',  # 周一至周五
            hour=9,
            minute=0,
            second=0
        ),
        id='new_stock_notification'
    )
    
    print("定时任务已设置，将于每个交易日9:00执行")
    scheduler.start()

if __name__ == "__main__":
    # 直接执行一次测试
    notify_new_stocks()
    
    # 设置定时任务
    # schedule_daily_job()