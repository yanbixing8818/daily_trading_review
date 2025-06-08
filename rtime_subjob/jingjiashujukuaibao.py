from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
from datetime import datetime
from chinese_calendar import is_workday
from core.utils import schedule_trade_day_jobs


# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=e875a0032d7f7884c9f2c65e454e7f89c9c296b872218dbe939647b11a708403"
SECRET = "SEC0c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8c8"  # 请替换为你的加签密钥
KEYWORD = "9.28竞价数据快报"  # 钉钉机器人的关键词

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
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": "股票监控提醒",
            "text": content + "\n\n**关键词：股票监控提醒**"  # 必须包含自定义关键词
        }
    }
    response = requests.post(DINGTALK_WEBHOOK, json=data, headers=headers)
    print(f"消息发送状态: {response.status_code}")


def jingjiashujukuaibao():
    """定时任务主逻辑"""
    if not is_workday(datetime.now()):  # 排除节假日和周末
        return
    data = get_auction_data()
    if data is not None:
        # 生成Markdown表格
        markdown_content = "### 🕘 9:27 竞价数据快报\n"
        markdown_content += "| 代码 | 名称 |\n"
        markdown_content += "|------|------|\n"
        for _, row in data.iterrows():
            # print(data)
            markdown_content += f"| {row['股票代码']}  | {row['股票简称']} |\n"
        dingtalk_markdown(markdown_content)

def jingjiashujukuaibao_rtime_jobs():
    times = [(9, 27)]
    schedule_trade_day_jobs(jingjiashujukuaibao, times)

if __name__ == "__main__":
    jingjiashujukuaibao_rtime_jobs()




