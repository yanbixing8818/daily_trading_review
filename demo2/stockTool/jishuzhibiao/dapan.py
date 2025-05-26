import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta


def get_realtime_data(symbol='sh000001'):
    # 获取实时数据
    spot_data = ak.stock_zh_index_spot_sina()
    print(spot_data)
    return spot_data[spot_data['代码'] == symbol].iloc[0]


def get_historical_data(symbol='sh000001', end_date=None):
    # 获取历史数据
    df = ak.stock_zh_index_daily(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    if end_date:
        end_date = pd.to_datetime(end_date)
        df = df[df.index <= end_date]

    return df


def calculate_5day_ma(df, realtime_open):
    # 使用实时开盘价和前4日收盘价计算5日线
    last_5_days = df.tail(5);
    #print(last_5_days)
    ma_5 = (realtime_open +
            last_5_days['close'].iloc[-1] +
            last_5_days['close'].iloc[-2] +
            last_5_days['close'].iloc[-3] +
            last_5_days['close'].iloc[-4]) / 5
    return ma_5


def plot_candlestick(df, realtime_data, ma_5):
    fig = go.Figure()

    # 添加K线图
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='red',  # Red for positive changes
        decreasing_line_color='green',
        name='K线'
    ))

    # 添加最新的实时数据点
    fig.add_trace(go.Scatter(
        x=[pd.to_datetime(datetime.now())],
        y=[float(realtime_data['最新价'])],
        mode='markers',
        marker=dict(color='red', size=10),
        name='实时价格'
    ))

    # 添加5日均线
    ma_5_series = df['close'].rolling(window=5).mean()
    ma_5_series.iloc[-1] = ma_5  # 用我们计算的最新5日均线替换最后一个值
    fig.add_trace(go.Scatter(
        x=ma_5_series.index,
        y=ma_5_series,
        mode='lines',
        name='5日均线',
        line=dict(color='orange', width=2)
    ))

    # 设置图表布局
    fig.update_layout(
        title='A股大盘指数实时K线图与5日均线',
        yaxis_title='价格',
        xaxis_rangeslider_visible=False
    )

    return fig

def app():
    # Streamlit应用
    st.title('A股大盘分析')

    # 获取实时数据
    realtime_data = get_realtime_data()

    # 获取历史数据
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)  # 显示最近30天的数据
    df = get_historical_data('sh000001', end_date)
    df = df.last('30D')

    # 计算5日均线
    ma_5 = calculate_5day_ma(df, float(realtime_data['今开']))

    # 绘制K线图和5日均线
    fig = plot_candlestick(df, realtime_data, ma_5)
    st.plotly_chart(fig, use_container_width=True)

    # 显示实时数据和计算结果
    st.subheader('实时数据')
    st.write(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.write(f"股票代码: {realtime_data['代码']}")
    st.write(f"股票名称: {realtime_data['名称']}")
    st.write(f"开盘价: {realtime_data['今开']}")
    st.write(f"当前价: {realtime_data['最新价']}")
    st.write(f"涨跌幅: {realtime_data['涨跌幅']}%")

    st.subheader('5日均线计算')
    st.write(f"最新5日均线: {ma_5:.2f}")

    # 显示用于计算的历史数据
    st.subheader('历史数据（用于计算）')
    st.dataframe(df[['open', 'close']].tail())