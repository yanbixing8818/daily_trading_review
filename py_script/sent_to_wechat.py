from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
from datetime import datetime
from chinese_calendar import is_workday

# 企业微信机器人配置（需关闭加签验证）
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"

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
    """发送Markdown格式消息到企业微信"""
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    response = requests.post(WECHAT_WEBHOOK, json=data, headers=headers)
    print(f"消息发送状态: {response.status_code}")

def job():
    """定时任务主逻辑"""
    # if not is_workday(datetime.now()):  # 排除节假日和周末
    #     return
    data = get_auction_data()
    if data is not None:
        # 生成Markdown表格
        markdown_content = "### 🕘 9:28 竞价数据快报\n"
        markdown_content += "| 代码 | 名称 |\n"
        markdown_content += "|------|------|\n"
        for _, row in data.iterrows():
            print(data)
            markdown_content += f"| {row['股票代码']}  | {row['股票简称']} |\n"
        dingtalk_markdown(markdown_content)

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    # 设置周一至周五9:28执行
    scheduler.add_job(
        job,
        CronTrigger(day_of_week='mon-fri', hour=13, minute=8)
        #CronTrigger(day_of_week='*', hour=9, minute=20)
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()