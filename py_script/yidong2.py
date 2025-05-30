import akshare as ak
import pandas as pd
import os
from core.crawling.stock_hist_em import stock_zh_a_hist

#计算异动情况，整体思路是，通过stock_zh_a_spot_em获取所有的股票代码，然后遍历股票代码，通过stock_zh_a_hist
#获取股票的日线数据，然后计算股票的异动情况。
#最好使用mysql来操作。



def main():
    stock_zh_a_hist_df = stock_zh_a_hist(
        symbol="688648",
        period="daily",
        start_date="20250429",
        end_date="20250529",
        adjust="qfq",
    )
    print(stock_zh_a_hist_df)
    # 按日期降序排列
    date_col = '日期' if '日期' in stock_zh_a_hist_df.columns else 'date'
    stock_zh_a_hist_df = stock_zh_a_hist_df.sort_values(by=date_col, ascending=False)
    # 保存到csv
    stock_zh_a_hist_df.to_csv("./data/688648_hist.csv", index=False)

    # 计算最大涨幅及起止日期
    calc_max_gain_window("./data/688648_hist.csv", 10)
    calc_max_gain_window("./data/688648_hist.csv", 20)

def calc_max_gain_window(csv_path, window):
    df = pd.read_csv(csv_path)
    close_col = None
    for col in ['收盘', 'close', '收盘价']:
        if col in df.columns:
            close_col = col
            break
    if close_col is None:
        raise ValueError("未找到收盘价列")
    date_col = '日期' if '日期' in df.columns else 'date'
    # 保持原始降序顺序，不排序
    closes = df[close_col].values
    dates = df[date_col].values

    max_gain_pct = float('-inf')
    max_buy_date = None
    max_sell_date = None
    max_buy_price = None
    max_sell_price = None

    n = len(closes)
    for i in range(n - window + 1):
        sell_idx = i
        buy_idx = i + window - 1
        sell_price = closes[sell_idx]
        buy_price = closes[buy_idx]
        gain_pct = (sell_price - buy_price) / buy_price * 100
        if gain_pct > max_gain_pct:
            max_gain_pct = gain_pct
            max_buy_date = dates[buy_idx]
            max_sell_date = dates[sell_idx]
            max_buy_price = buy_price
            max_sell_price = sell_price

    if max_gain_pct > float('-inf'):
        print(f"{window}日窗口最大涨幅: {max_gain_pct:.2f}%")
        print(f"买入日期: {max_buy_date}，买入价: {max_buy_price}")
        print(f"卖出日期: {max_sell_date}，卖出价: {max_sell_price}")
    else:
        print(f"{window}日窗口没有可用的区间")

if __name__ == "__main__":
    
    main()
