import akshare as ak
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import io
import streamlit as st

# 设置Matplotlib字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体为黑体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def get_trade_dates_last_n(n=30):
    trade_date_df = ak.tool_trade_date_hist_sina()
    trade_date_df['trade_date'] = pd.to_datetime(trade_date_df['trade_date'], format='%Y-%m-%d')
    trade_date_df = trade_date_df.sort_values('trade_date')
    today = pd.to_datetime(datetime.today().date())
    if today in trade_date_df['trade_date'].values:
        idx = trade_date_df[trade_date_df['trade_date'] == today].index[0]
        selected = trade_date_df.loc[:idx].tail(n)
    else:
        selected = trade_date_df.tail(n)
    trade_dates = selected['trade_date'].dt.strftime('%Y%m%d').tolist()
    return trade_dates

def get_limit_up_down_stocks(trade_dates):
    limit_up_counts = []
    limit_down_counts = []
    for date in trade_dates:
        try:
            limit_up_stocks = ak.stock_zt_pool_em(date=date)
            limit_down_stocks = ak.stock_zt_pool_dtgc_em(date=date)
            limit_up_counts.append((date, len(limit_up_stocks)))
            limit_down_counts.append((date, len(limit_down_stocks)))
        except Exception as e:
            print(f"Error fetching data for {date}: {e}")
    return limit_up_counts, limit_down_counts

def app():
    # 默认统计前15个交易日
    trade_dates = get_trade_dates_last_n(15)
    limit_up_counts, limit_down_counts = get_limit_up_down_stocks(trade_dates)

    limit_up_df = pd.DataFrame(limit_up_counts, columns=['日期', '涨停数量'])
    limit_down_df = pd.DataFrame(limit_down_counts, columns=['日期', '跌停数量'])

    result_df = pd.merge(limit_up_df, limit_down_df, on='日期')
    print(result_df)

    # result_df.to_excel('recent_30_days_limit_up_down.xlsx', index=False)

    plt.figure(figsize=(24, 12))
    sns.lineplot(x='日期', y='涨停数量', data=result_df, label='涨停数量', color='red')
    sns.lineplot(x='日期', y='跌停数量', data=result_df, label='跌停数量', color='green')
    plt.title('近15个交易日涨跌停数量变化', fontsize=24)
    plt.xlabel('日期', fontsize=18)
    plt.ylabel('数量', fontsize=18)
    plt.xticks(ticks=range(len(result_df)), labels=result_df['日期'], rotation=45, fontsize=14)
    plt.yticks(fontsize=14)
    plt.legend()
    plt.grid(axis='x', linestyle='--', color='gray', alpha=0.5)  # 添加竖线
    plt.tight_layout()
    # 标注数值
    for i, row in result_df.iterrows():
        plt.text(i, row['涨停数量'], str(row['涨停数量']), ha='center', va='bottom', fontsize=18, color='red')
        plt.text(i, row['跌停数量'], str(row['跌停数量']), ha='center', va='bottom', fontsize=18, color='green')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=500)
    buf.seek(0)
    st.image(buf, caption='涨停和跌停数量随时间变化', use_container_width=True)
    plt.close()

if __name__ == "__main__":
    app()