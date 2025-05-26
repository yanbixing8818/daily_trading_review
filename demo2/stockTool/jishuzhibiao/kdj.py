import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta


def calculate_kdj(df, n=9, m1=3, m2=3):

    low_list = df['low'].rolling(window=n, min_periods=1).min()
    high_list = df['high'].rolling(window=n, min_periods=1).max()
    rsv = (df['close'] - low_list) / (high_list - low_list) * 100

    df['K'] = pd.DataFrame(rsv).ewm(com=m1 - 1, adjust=False).mean()
    df['D'] = df['K'].ewm(com=m2 - 1, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']

    return df


def detect_crosses(df):
    df['Golden_Cross'] = (df['K'] > df['D']) & (df['K'].shift(1) <= df['D'].shift(1))
    df['Death_Cross'] = (df['K'] < df['D']) & (df['K'].shift(1) >= df['D'].shift(1))
    return df


def plot_candlestick_kdj(df):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])

    # Candlestick chart
    fig.add_trace(go.Candlestick(x=df.index,
                                 open=df['open'],
                                 high=df['high'],
                                 low=df['low'],
                                 close=df['close'],
                                 increasing_line_color='red',
                                 decreasing_line_color='green',
                                 name='K线'), row=1, col=1)

    # KDJ lines
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], mode='lines', name='K', line=dict(color='blue')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], mode='lines', name='D', line=dict(color='orange')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['J'], mode='lines', name='J', line=dict(color='purple')), row=2, col=1)

    # Golden crosses
    golden_crosses = df[df['Golden_Cross']]
    fig.add_trace(go.Scatter(x=golden_crosses.index, y=golden_crosses['K'], mode='markers',
                             name='金叉', marker=dict(symbol='triangle-up', size=10, color='red')), row=2, col=1)

    # Death crosses
    death_crosses = df[df['Death_Cross']]
    fig.add_trace(go.Scatter(x=death_crosses.index, y=death_crosses['K'], mode='markers',
                             name='死叉', marker=dict(symbol='triangle-down', size=10, color='green')), row=2, col=1)

    fig.update_layout(title='股票K线图和KDJ指标（最近3个月）', xaxis_rangeslider_visible=False, height=800)
    fig.update_xaxes(title_text='日期', row=2, col=1)
    fig.update_yaxes(title_text='价格', row=1, col=1)
    fig.update_yaxes(title_text='KDJ值', row=2, col=1)

    return fig


def app():
    st.title('股票KDJ金叉死叉预警系统')

    # 用户输入股票代码
    stock_code = st.text_input('请输入股票代码（例如：sh000001 表示上证指数）:', 'sh000001')

    if st.button('分析'):
        try:
            # 使用 AKShare 获取股票数据
            with st.spinner('正在获取股票数据...'):
                end_date = datetime.now()
                #end_date = datetime(2024, 12, 31)
                start_date = end_date - timedelta(days=90)  # 获取最近3个月的数据

                if stock_code.startswith('sh') or stock_code.startswith('sz'):
                    df = ak.stock_zh_index_daily(symbol=stock_code)
                else:
                    df = ak.stock_zh_a_daily(symbol=stock_code)

            # 重命名列
            df = df.rename(columns={
                "date": "Date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close"
            })

            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)

            # 筛选最近3个月的数据
            df = df.loc[start_date:end_date]

            # 计算KDJ指标
            df = calculate_kdj(df)
            df = detect_crosses(df)

            # 绘制K线图和KDJ图
            st.plotly_chart(plot_candlestick_kdj(df))

            # 输出最近的金叉和死叉
            recent_crosses = df[df['Golden_Cross'] | df['Death_Cross']].tail(5)

            st.subheader('最近的KDJ交叉信号：')
            for date, row in recent_crosses.iterrows():
                if row['Golden_Cross']:
                    st.write(f"{date.date()}: 金叉 (K: {row['K']:.2f}, D: {row['D']:.2f})")
                elif row['Death_Cross']:
                    st.write(f"{date.date()}: 死叉 (K: {row['K']:.2f}, D: {row['D']:.2f})")

            # 检查最新的数据点是否接近交叉
            latest = df.iloc[-1]
            if abs(latest['K'] - latest['D']) < 1:  # 你可以调整这个阈值
                st.warning(f"警告：最新数据点 ({latest.name.date()}) 接近交叉！")
                st.write(f"K: {latest['K']:.2f}, D: {latest['D']:.2f}")

            st.subheader(f'当前KDJ值 (日期: {latest.name.date()}):')
            st.write(f"K: {latest['K']:.2f}")
            st.write(f"D: {latest['D']:.2f}")
            st.write(f"J: {latest['J']:.2f}")

        except Exception as e:
            st.error(f'发生错误: {str(e)}')
            st.error('请确保输入了正确的股票代码。对于上证指数，请使用 sh000001；对于个股，请使用类似 sh600000 的格式。')


if __name__ == "__main__":
    app()

