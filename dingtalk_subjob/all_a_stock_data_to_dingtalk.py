import akshare as ak
import pandas as pd
import numpy as np
import plotly.express as px
import io
from core.dingtalk.dingtalk_usage import send_to_dingtalk

def fetch_market_data():
    try:
        # 使用AKShare获取A股市场现货数据
        stock_zh_a_spot_df = ak.stock_zh_a_spot_em()
        return stock_zh_a_spot_df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None

def calculate_market_overview(df):
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

def calculate_stock_distribution(df):
    bins = [-np.inf, -10, -7, -5, -3, 0, 3, 5, 7, 10, np.inf]
    labels = ['跌幅10%以上', '跌幅7%-10%', '跌幅5%-7%', '跌幅3%-5%', '跌幅0%-3%',
              '涨幅0%-3%', '涨幅3%-5%', '涨幅5%-7%', '涨幅7%-10%', '涨幅10%以上']
    df['distribution'] = pd.cut(df['涨跌幅'], bins=bins, labels=labels)
    distribution = df['distribution'].value_counts().sort_index()
    return distribution

def plot_distribution(distribution):
    fig = px.bar(
        x=distribution.index,
        y=distribution.values,
        labels={'x': '涨跌幅区间', 'y': '股票数量'},
        title="市场涨跌分布"
    )
    fig.update_traces(marker_color=['red'if'涨'in x else'green'for x in distribution.index],
                      text=distribution.values,  # 在条形上显示数量
                      textposition='auto')  # 自动放置文本位置
    return fig

def send_all_a_stock_data_to_dingtalk():
    stock_zh_a_spot_df = fetch_market_data()
    if stock_zh_a_spot_df is not None:
        # 计算市场概览
        overview = calculate_market_overview(stock_zh_a_spot_df)
        print("市场概览:")
        for k, v in overview.items():
            print(f"{k}: {v}")
        # 计算股票分布
        distribution = calculate_stock_distribution(stock_zh_a_spot_df)
        # 生成分布图并推送到钉钉
        fig_dist = plot_distribution(distribution)
        buf = io.BytesIO()
        fig_dist.write_image(buf, format='png', scale=2)
        buf.seek(0)
        send_to_dingtalk(buf, "A股市场涨跌分布")

if __name__ == "__main__":
    send_all_a_stock_data_to_dingtalk()