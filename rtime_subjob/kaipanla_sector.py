import requests
import datetime
import json
import os
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from core.trade_time import is_trade_date

# ================= 配置文件 =================
HISTORY_FILE = 'sector_ranking.json'  # 板块排名历史记录文件
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=40b6a6a19c21011d660f9b253995ef6288b60a15d91be256b23fc94c6d7431cf"
KEYWORD = "盘中板块强度"  # 钉钉机器人自定义关键字（必须与设置完全匹配）


# ================= 股票数据获取函数 =================
def get_sector_data(date, k):
    url = "https://apphq.longhuvip.com/w1/api/index.php" if k == 0 else "https://apphis.longhuvip.com/w1/api/index.php"

    headers = {
        "Host": "apphq.longhuvip.com" if k == 0 else "apphis.longhuvip.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "lhb/5.17.9 (com.kaipanla.www; build:0; iOS 16.6.0) Alamofire/4.9.1"
    }

    params = {
        "Date": date if k == 1 else datetime.date.today().strftime("%Y-%m-%d"),
        "Index": "0",
        "Order": "1",
        "PhoneOSNew": "2",
        "Type": "1",
        "VerSion": "5.17.0.9",
        "ZSType": "7",
        "a": "RealRankingInfo",
        "apiv": "w38",
        "c": "ZhiShuRanking",
        "st": "20"
    }

    try:
        response = requests.post(url, headers=headers, data=params)
        if response.status_code == 200:
            data = response.json()
            if "list" in data and data["list"]:
                return [
                    {"代码": item[0], "名称": item[1], "强度": item[2], "涨幅%": item[3]}
                    for item in data["list"] if len(item) >= 4
                ]
    except Exception as e:
        print(f"板块数据获取失败: {str(e)}")
    return []


def get_stock_data(sector_code, date, k):
    url = "https://apphq.longhuvip.com/w1/api/index.php" if k == 0 else "https://apphis.longhuvip.com/w1/api/index.php"

    headers = {
        "Host": "apphq.longhuvip.com" if k == 0 else "apphis.longhuvip.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "lhb/5.17.9 (com.kaipanla.www; build:0; iOS 16.6.0) Alamofire/4.9.1"
    }

    params = {
        "PlateID": sector_code,
        "Date": date if k == 1 else datetime.date.today().strftime("%Y-%m-%d"),
        "Index": "0",
        "Order": "1",
        "PhoneOSNew": "2",
        "Type": "6",
        "VerSion": "5.17.0.9",
        "a": "ZhiShuStockList_W8",
        "apiv": "w38",
        "c": "ZhiShuRanking",
        "st": "20"
    }

    try:
        response = requests.post(url, headers=headers, data=params)
        if response.status_code == 200:
            data = response.json()
            if "list" in data and data["list"]:
                return [
                    {"代码": item[0], "名称": item[1], "涨幅%": item[6], "连板": item[23], "板块": item[4]}
                    for item in data["list"] if len(item) >= 24 and item[6] != "-"
                ]
    except Exception as e:
        print(f"个股数据获取失败: {str(e)}")
    return []


# ================= 板块排名历史管理 =================
def load_sector_history():
    """加载历史板块排名数据"""
    if not os.path.exists(HISTORY_FILE):
        return None

    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return None


def save_sector_history(top_sectors):
    """保存当前板块排名"""
    data = {
        'date': datetime.date.today().strftime("%Y-%m-%d"),
        'top3': [s['代码'] for s in top_sectors]  # 只存储代码避免名称变化干扰[3](@ref)
    }
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f)


def check_ranking_changes(new_top_sectors):
    """检查板块排名变化"""
    history = load_sector_history()

    # 首次运行或没有历史记录
    if not history:
        return True

    # 比较当前前三名和历史前三名的板块代码
    old_top3 = history.get('top3', [])
    new_top3 = [s['代码'] for s in new_top_sectors]

    return old_top3 != new_top3


# ================= 钉钉消息推送 =================
def format_stock_link(stock_code, stock_name):
    """生成股票Markdown超链接"""
    return f"[{stock_name}](https://stockpage.10jqka.com.cn/{stock_code}/)"


def send_dingtalk_message(content):
    """发送Markdown格式消息到钉钉（使用自定义关键字）"""
    headers = {'Content-Type': 'application/json'}
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "股票监控",
            "text": f"**{KEYWORD}**\n{content}"  # 包含自定义关键字[7](@ref)
        }
    }
    try:
        response = requests.post(DINGTALK_WEBHOOK, headers=headers, json=payload)
        if response.json().get("errcode") == 0:
            print("钉钉消息发送成功")
        else:
            print(f"发送失败: {response.text}")
    except Exception as e:
        print(f"钉钉消息发送异常: {str(e)}")


# ================= 核心业务逻辑 =================
def fetch_and_send():
    now = datetime.datetime.now()
    # 判断是否为交易日
    if not is_trade_date(now.date()):
        print("非交易日，不执行任务")
        return
    # 判断是否在9:20~15:00之间
    if not (datetime.time(9, 20) <= now.time() < datetime.time(15, 0)):
        print("非指定时间段，不执行任务")
        return
    try:
        date_str = datetime.date.today().strftime("%Y-%m-%d")
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')} 开始获取板块数据...")

        # 获取所有板块数据
        sectors = get_sector_data(date_str, k=0)

        if not sectors:
            print("未获取到板块数据")
            return

        # 获取强度前三的板块（过滤无效值）
        top_sectors = sorted(
            [s for s in sectors if s["强度"] != "-"],
            key=lambda x: float(x["强度"]),
            reverse=True
        )[:3]

        #检查排名变化
        if not check_ranking_changes(top_sectors):
            print("板块排名未变化，无需发送通知")
            return

        print("板块排名变化，准备发送通知...")

        # 构建Markdown消息
        content = f"#### 📊 板块排名变化 {datetime.datetime.now().strftime('%m-%d %H:%M')}\n\n"

        for i, sector in enumerate(top_sectors):
            # 获取该板块涨幅前三的个股
            stocks = get_stock_data(sector["代码"], date_str, k=0)
            top_stocks = sorted(
                stocks,
                key=lambda x: float(x["涨幅%"]),
                reverse=True
            )[:3]

            # 添加板块信息
            content += f"**TOP{i + 1} {sector['名称']}** `强度:{sector['强度']} 涨幅:{sector['涨幅%']}%`\n"

            # 添加个股信息
            for j, stock in enumerate(top_stocks):
                arrow = "📈" if float(stock["涨幅%"]) > 0 else "📉"
                stock_link = format_stock_link(stock["代码"], stock["名称"])
                content += f"> {j + 1}. {stock_link} {arrow} **{stock['涨幅%']}%**"
                content += f" 连板:{stock['连板']}\n"

            content += "\n"


        # 发送钉钉消息
        send_dingtalk_message(content)

        # 保存当前排名
        save_sector_history(top_sectors)
        print("板块排名已保存")

    except Exception as e:
        print(f"任务执行异常: {str(e)}")


# ================= 定时任务调度 =================
if __name__ == "__main__":
    # 初始化历史文件（如果不存在）
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w') as f:
            json.dump({'date': '', 'top3': []}, f)
    # fetch_and_send()
    
    scheduler = BlockingScheduler()
    # 每分钟执行一次（交易时段可调整为更频繁）
    scheduler.add_job(fetch_and_send, 'interval', minutes=1)

    print("=" * 50)
    print("股票板块监控服务已启动")
    print(f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"历史记录文件: {os.path.abspath(HISTORY_FILE)}")
    print("=" * 50)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("服务已停止")