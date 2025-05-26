# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime


# 神奇九转核心算法
def calculate_nine_turns(df):
    """计算九转序列"""
    df['up_condition'] = df['close'] > df['close'].shift(4)
    df['down_condition'] = df['close'] < df['close'].shift(4)

    # 连续计数逻辑
    for condition in ['up', 'down']:
        streak = 0
        streaks = []
        for idx in range(len(df)):
            if df[f'{condition}_condition'].iloc[idx]:
                streak = streak + 1 if streak < 9 else 9
            else:
                streak = 0
            streaks.append(streak)
        df[f'{condition}_streak'] = streaks

    # 生成买卖信号
    df['ma20'] = df['close'].rolling(20).mean()
    #df['buy_signal'] = (df['down_streak'] == 9) & (df['close'] > df['ma20'])
    df['buy_signal'] = (df['down_streak'] == 9)
    #df['sell_signal'] = (df['up_streak'] == 9) & (df['close'] < df['ma20'])
    df['sell_signal'] = (df['up_streak'] == 9)
    return df


# 数据获取
def get_stock_data(symbol, start, end):
    """获取A股前复权数据"""
    try:
        code = f"{symbol}"
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq"
        )
        df = df.rename(columns={
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume'
        })
        df['date'] = pd.to_datetime(df['date'])
        return df.set_index('date').sort_index()
    except Exception as e:
        st.error(f"数据获取失败：{str(e)}")
        return None


# 可视化
def plot_kline_with_signals(df):
    fig = go.Figure()

    # 主K线
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='#FF4500',
        decreasing_line_color='#1E90FF',
        name='K线'
    ))

    # 九转标记
    up_points = df[df['up_streak'] >= 1]
    down_points = df[df['down_streak'] >= 1]
    # up_points = df[df['up_streak'] >= 6]
    # down_points = df[df['down_streak'] >= 6]

    # 上涨序列
    fig.add_trace(go.Scatter(
        x=up_points.index,
        y=up_points['high'] * 1.02,
        mode='text',
        text=up_points['up_streak'].astype(str),
        textfont=dict(color='#FF4500', size=14),
        name='上涨九转'
    ))

    # 下跌序列
    fig.add_trace(go.Scatter(
        x=down_points.index,
        y=down_points['low'] * 0.98,
        mode='text',
        text=down_points['down_streak'].astype(str),
        textfont=dict(color='#1E90FF', size=14),
        name='下跌九转'
    ))

    # 买卖信号
    buy_signals = df[df['buy_signal']]
    sell_signals = df[df['sell_signal']]

    fig.add_trace(go.Scatter(
        x=buy_signals.index,
        y=buy_signals['low'] * 0.95,
        mode='markers',
        marker=dict(color='green', size=12, symbol='triangle-up'),
        name='买入信号'
    ))

    fig.add_trace(go.Scatter(
        x=sell_signals.index,
        y=sell_signals['high'] * 1.05,
        mode='markers',
        marker=dict(color='red', size=12, symbol='triangle-down'),
        name='卖出信号'
    ))

    fig.update_layout(
        title='神奇九转策略分析',
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        height=600
    )
    return fig


def app():
    st.title("A股神奇九转策略分析系统")
    code = st.text_input("股票代码", "600519")
    start_date = st.date_input("开始日期", datetime(2024, 10, 8))
    end_date = st.date_input("结束日期", datetime.now())
    show_volume = st.checkbox("显示成交量分析", True)
    data = get_stock_data(code, start_date, end_date)
    if data is not None:
        analyzed_data = calculate_nine_turns(data)

    # 主显示区
    col1, col2 = st.columns([3, 1])

    with col1:
        st.plotly_chart(plot_kline_with_signals(analyzed_data), use_container_width=True)

    with col2:
        st.subheader("实时信号")
        if analyzed_data['buy_signal'].any():
            last_buy = analyzed_data[analyzed_data['buy_signal']].iloc[-1]
            st.success(f"""
            ​**买入信号**  
            {last_buy.name.strftime('%Y-%m-%d')}  
            价格：{last_buy['close']:.2f}  
            """)

        if analyzed_data['sell_signal'].any():
            last_sell = analyzed_data[analyzed_data['sell_signal']].iloc[-1]
            st.error(f"""
            ​**卖出信号**  
            {last_sell.name.strftime('%Y-%m-%d')}  
            价格：{last_sell['close']:.2f}  
            """)

    # 成交量分析
    if show_volume:
        st.subheader("成交量分析")
        df_vol = analyzed_data[['volume']].copy()
        df_vol['vol_ma5'] = df_vol['volume'].rolling(5).mean()
        st.area_chart(df_vol, use_container_width=True)

if __name__ == "__main__":
    app()

