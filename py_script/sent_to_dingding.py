from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
import hmac
import hashlib
import base64
import urllib.parse
import time
from datetime import datetime
from chinese_calendar import is_workday

# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=xxxxxx"
SECRET = "SEC0c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8"  # 请替换为你的加签密钥
KEYWORD = "竞价数据"  # 钉钉机器人的关键词

def get_sign():
    """生成钉钉机器人签名"""
    timestamp = str(round(time.time() * 1000))
    secret_enc = SECRET.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, SECRET)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign

def get_auction_data():
    """获取竞价排名前10的股票数据"""
    try:
        query = "非ST，竞价涨停"   #改成自己的策略
        df = pywencai.get(query=query, sort_key='竞价涨停封单金额', sort_order='desc')
        return df[['股票代码', '股票简称']].head(10)
    except Exception as e:
        print(f"数据获取失败: {str(e)}")
        return None

def dingtalk_markdown(content):
    """发送Markdown格式消息到钉钉"""
    timestamp, sign = get_sign()
    webhook = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"{KEYWORD}竞价数据快报",
            "text": f"{KEYWORD} {content}"  # 在内容开头添加关键词
        },
        "at": {
            "isAtAll": False  # 是否@所有人
        }
    }
    
    try:
        response = requests.post(webhook, json=data, headers=headers)
        response.raise_for_status()  # 检查响应状态
        print(f"消息发送状态: {response.status_code}")
        print(f"响应内容: {response.json()}")
    except Exception as e:
        print(f"消息发送失败: {str(e)}")

def job():
    """定时任务主逻辑"""
    if not is_workday(datetime.now()):  # 排除节假日和周末
        return
        
    data = get_auction_data()
    if data is not None:
        # 生成Markdown表格
        markdown_content = "### 🕘 9:28 竞价数据快报\n"
        markdown_content += "| 代码 | 名称 |\n"
        markdown_content += "|------|------|\n"
        for _, row in data.iterrows():
            markdown_content += f"| {row['股票代码']}  | {row['股票简称']} |\n"
        dingtalk_markdown(markdown_content)

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    # 设置周一至周五9:28执行
    scheduler.add_job(
        job,
        CronTrigger(day_of_week='mon-fri', hour=13, minute=44)
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()