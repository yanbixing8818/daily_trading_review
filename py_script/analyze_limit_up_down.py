import akshare as ak
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# 设置Matplotlib字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体为黑体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def get_trade_dates(start_date, end_date):
    trade_date_df = ak.tool_trade_date_hist_sina()
    trade_date_df['trade_date'] = pd.to_datetime(trade_date_df['trade_date'], format='%Y-%m-%d')
    mask = (trade_date_df['trade_date'] >= start_date) & (trade_date_df['trade_date'] <= end_date)
    trade_dates = trade_date_df.loc[mask, 'trade_date'].dt.strftime('%Y%m%d').tolist()
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

def main():
    start_date = datetime.strptime('2025-04-01', '%Y-%m-%d')
    end_date = datetime.strptime('2025-05-14', '%Y-%m-%d')

    trade_dates = get_trade_dates(start_date, end_date)
    limit_up_counts, limit_down_counts = get_limit_up_down_stocks(trade_dates)

    limit_up_df = pd.DataFrame(limit_up_counts, columns=['日期', '涨停数量'])
    limit_down_df = pd.DataFrame(limit_down_counts, columns=['日期', '跌停数量'])

    result_df = pd.merge(limit_up_df, limit_down_df, on='日期')
    print(result_df)

    result_df.to_excel('recent_30_days_limit_up_down.xlsx', index=False)

    plt.figure(figsize=(14, 7))
    sns.lineplot(x='日期', y='涨停数量', data=result_df, label='涨停数量')
    sns.lineplot(x='日期', y='跌停数量', data=result_df, label='跌停数量')
    plt.title('涨停和跌停数量随时间变化')
    plt.xlabel('日期')
    plt.ylabel('数量')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig("output.png", dpi=300)
    # plt.show()

if __name__ == "__main__":
    main()