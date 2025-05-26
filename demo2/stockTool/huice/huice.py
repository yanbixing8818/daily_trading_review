import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
def fetch_stock_data(stock_code, start_date, end_date):
    # 获取股票历史数据
    stock_data = ak.stock_zh_a_daily(symbol=stock_code, start_date=start_date, end_date=end_date)
    stock_data.reset_index(inplace=True)  # 重置索引
    stock_data['date'] = pd.to_datetime(stock_data['date'])  # 转换日期格式
    stock_data.set_index('date', inplace=True)  # 将日期设置为索引
    return stock_data

def calculate_max_drawdown(prices):
    cumulative_returns = (1 + prices).cumprod()
    peak = cumulative_returns.cummax()
    drawdown = (cumulative_returns - peak) / peak
    max_drawdown = drawdown.min()  # 最大回撤
    return max_drawdown

def app():
    st.title("股票回测与K线图")

    # 输入股票代码
    stock_code = st.text_input("输入股票代码（如 sh600000）:", "sh600000")

    # 输入开始和结束时间
    start_date = st.date_input("选择开始时间:", pd.to_datetime("2024-10-08"))
    end_date = st.date_input("选择结束时间:", pd.to_datetime("2024-12-27"))

    if st.button("获取数据"):
        # 获取股票数据
        stock_data = fetch_stock_data(stock_code, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"))

        # 计算每日收益率
        stock_data['returns'] = stock_data['close'].pct_change()

        # 计算最大回撤率
        max_drawdown = calculate_max_drawdown(stock_data['returns'].fillna(0))  # 填充NaN值
        st.write(f"最大回撤率: {max_drawdown:.2%}")

        # 计算总收益率
        total_return = (stock_data['close'].iloc[-1] / stock_data['close'].iloc[0]) - 1
        st.write(f"总收益率: {total_return:.2%}")


        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

        # 绘制K线图
        fig.add_trace(go.Candlestick(x=stock_data.index,
                                               open=stock_data['open'],
                                               high=stock_data['high'],
                                               low=stock_data['low'],
                                               close=stock_data['close'],
                                               increasing_line_color='red',
                                               decreasing_line_color='green',
                                               name='K线图'))
        fig.add_trace(go.Bar(
            x=stock_data.index,
            y=stock_data['volume'],
            name='成交量',
            marker_color='rgba(0, 0, 255, 0.5)'
        ), row=2, col=1)

        ma5 = stock_data['close'].rolling(window=5).mean()
        ma10 = stock_data['close'].rolling(window=10).mean()
        ma20 = stock_data['close'].rolling(window=20).mean()

        fig.add_trace(go.Scatter(x=stock_data.index, y=ma5, name='MA5', line=dict(color='blue', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=stock_data.index, y=ma10, name='MA10', line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=stock_data.index, y=ma20, name='MA20', line=dict(color='green', width=1)), row=1, col=1)

        fig.update_layout(title=f"{stock_code} K线图",
                          xaxis_title='日期',
                          yaxis_title='价格',
                          xaxis_rangeslider_visible=False)

        st.plotly_chart(fig)

if __name__ == "__main__":
    app()