from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pywencai
import requests
import pandas as pd
from datetime import datetime, timedelta
from chinese_calendar import is_workday
from core.utils import schedule_trade_day_jobs
import os
import sys
import re
import random
import time

# 添加ai_xgboost目录到路径
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai', 'ai_xgboost'))

# 钉钉机器人配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=e875a0032d7f7884c9f2c65e454e7f89c9c296b872218dbe939647b11a708403"
KEYWORD = "竞价选股"  # 钉钉机器人的关键词

def get_auction_data():
    """获取当天的竞价数据"""
    try:
        today = datetime.now()
        trade_date = today.strftime("%Y年%m月%d日")
        date_str = trade_date.replace("年", "").replace("月", "").replace("日", "")
        
        query = f"创业板,非st,{trade_date}竞价涨幅,{trade_date}竞价匹配价,竞价成交量,{trade_date}09:25分时换手率,{trade_date}09:25分时量比,{trade_date}竞价量，竞价金额, {trade_date}竞价未匹配量,{trade_date}竞价未匹配金额,竞价主力资金流向,{trade_date}流通市值竞价dde大单净额,竞价大单净额,竞价小单净额"
        data = pywencai.get(query=query, loop=True)
        
        if isinstance(data, pd.DataFrame) and not data.empty:
            # 去掉所有列名中的[YYYYMMDD]
            def remove_date_suffix(col):
                return re.sub(r'\[\d{8}\]', '', col).strip()
            data.columns = [remove_date_suffix(col) for col in data.columns]
            print(f"{trade_date} 获取到{len(data)}条记录，字段包括: {data.columns.tolist()}")
            
            # 保存到jingjia_base_data目录
            jingjia_base_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai', 'ai_xgboost', 'jingjia_base_data')
            os.makedirs(jingjia_base_data_dir, exist_ok=True)
            csv_path = os.path.join(jingjia_base_data_dir, f"bidding_data_{date_str}.csv")
            data.to_csv(csv_path, index=False, encoding="utf_8_sig")
            
            return csv_path, data
        else:
            print(f"{trade_date} 未获取到数据，请检查查询语句或Cookie！")
            return None, None
            
    except Exception as e:
        print(f"获取竞价数据失败: {str(e)}")
        return None, None

def predict_auction_stocks(csv_path):
    """调用jingjia_model进行预测"""
    try:
        from jingjia_model import predict_bidding_file
        
        # 模型文件路径
        jingjia_models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai', 'ai_xgboost', 'jingjia_models')
        xgb_model_path = os.path.join(jingjia_models_dir, 'xgb_model.json')
        lgb_model_path = os.path.join(jingjia_models_dir, 'lgb_model.txt')
        xgb_scaler_path = os.path.join(jingjia_models_dir, 'xgb_scaler.pkl')
        lgb_scaler_path = os.path.join(jingjia_models_dir, 'lgb_scaler.pkl')
        
        # 检查模型文件是否存在
        if not all(os.path.exists(p) for p in [xgb_model_path, lgb_model_path, xgb_scaler_path, lgb_scaler_path]):
            print("错误：模型文件不完整，请先运行main()训练模型")
            return None
        
        # 进行预测
        result = predict_bidding_file(
            csv_path=csv_path,
            xgb_model_path=xgb_model_path,
            lgb_model_path=lgb_model_path,
            xgb_scaler_path=xgb_scaler_path,
            lgb_scaler_path=lgb_scaler_path
        )
        
        return result
        
    except Exception as e:
        print(f"预测失败: {str(e)}")
        return None

def dingtalk_markdown(content):
    """发送Markdown格式消息到钉钉"""
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"9:26竞价预测结果 - {KEYWORD}",
            # 直接包含关键词本身，避免因前缀导致匹配失败
            "text": content + f"\n\n{KEYWORD}"
        }
    }
    response = requests.post(DINGTALK_WEBHOOK, json=data, headers=headers)
    try:
        print(f"钉钉返回: {response.status_code}, {response.text}")
    except Exception:
        print(f"钉钉返回: {response.status_code}")

def format_prediction_result(result):
    """格式化预测结果为Markdown格式"""
    if result is None or result.empty:
        return "### 🚨 竞价预测失败\n\n未能获取到有效的预测结果，请检查模型和数据。"
    
    markdown_content = "### 🎯 9:26竞价预测结果\n\n"
    markdown_content += "| 排名 | 股票代码 | 股票名称 | XGB概率 | LGB概率 | 融合概率 |\n"
    markdown_content += "|------|----------|----------|----------|----------|----------|\n"
    
    for i, (_, row) in enumerate(result.iterrows(), 1):
        code = row.get('股票代码', 'N/A')
        name = row.get('名称', 'N/A')
        xgb_prob = f"{row.get('xgb_proba', 0):.3f}" if pd.notna(row.get('xgb_proba')) else 'N/A'
        lgb_prob = f"{row.get('lgb_proba', 0):.3f}" if pd.notna(row.get('lgb_proba')) else 'N/A'
        fused_prob = f"{row.get('fused_proba', 0):.3f}" if pd.notna(row.get('fused_proba')) else 'N/A'
        
        markdown_content += f"| {i} | {code} | {name} | {xgb_prob} | {lgb_prob} | {fused_prob} |\n"
    
    markdown_content += f"\n**预测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    markdown_content += f"\n**预测数量**: {len(result)}只股票"
    
    return markdown_content

def jingjia_predict_alert():
    """定时任务主逻辑"""
    if not is_workday(datetime.now()):  # 排除节假日和周末
        print("非工作日，跳过执行")
        return
    
    print(f"开始执行竞价预测任务: {datetime.now()}")
    
    # 1. 获取竞价数据
    csv_path, data = get_auction_data()
    if csv_path is None:
        error_msg = "### 🚨 竞价数据获取失败\n\n未能获取到当天的竞价数据，请检查网络连接和查询语句。"
        dingtalk_markdown(error_msg)
        return
    
    # 2. 进行预测
    print("开始进行竞价预测...")
    result = predict_auction_stocks(csv_path)
    
    # 3. 格式化结果并发送钉钉
    if result is not None:
        markdown_content = format_prediction_result(result)
        print("预测完成，发送钉钉消息...")
        dingtalk_markdown(markdown_content)
        print("钉钉消息发送完成")
    else:
        error_msg = "### 🚨 竞价预测失败\n\n模型预测过程中出现错误，请检查模型文件和数据格式。"
        dingtalk_markdown(error_msg)

def jingjia_predict_alert_rtime_jobs():
    """设置定时任务，在交易日9:26执行"""
    times = [(9, 26)]
    schedule_trade_day_jobs(jingjia_predict_alert, times)

if __name__ == "__main__":
    # 测试模式：直接执行一次
    # print("测试模式：直接执行竞价预测")
    # jingjia_predict_alert()
    
    # 定时任务模式（注释掉测试模式后启用）
    jingjia_predict_alert_rtime_jobs() 