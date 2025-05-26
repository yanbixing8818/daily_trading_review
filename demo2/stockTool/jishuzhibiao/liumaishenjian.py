import akshare as ak
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta


# ================== 指标计算模块 ==================
def calculate_macd(df):
    """MACD指标（红:金叉, 绿:死叉）"""
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = ema12 - ema26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['DEA']
    df['MACD_Signal'] = np.where(df['DIF'] > df['DEA'], '红', '绿')
    return df


def calculate_kdj(df):
    """KDJ指标（红:K>D, 绿:K<D）"""
    low_min = df['low'].rolling(9).min()
    high_max = df['high'].rolling(9).max()
    rsv = (df['close'] - low_min) / (high_max - low_min + 1e-8) * 100
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    df['KDJ_Signal'] = np.where(df['K'] > df['D'], '红', '绿')
    return df


def calculate_rsi(df, period=14):
    """RSI指标（红:>50, 绿:<50）"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-8)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI_Signal'] = np.where(df['RSI'] > 50, '红', '绿')
    return df


def calculate_lwr(df, period=14):
    """LWR威廉指标（红:<20超卖, 绿:>80超买）"""
    highest = df['high'].rolling(period).max()
    lowest = df['low'].rolling(period).min()
    df['LWR'] = (highest - df['close']) / (highest - lowest + 1e-8) * 100
    df['LWR_Signal'] = np.where(df['LWR'] < 20, '红', '绿')
    return df


def calculate_bbi(df):
    """BBI多空指标（红:价格在BBI上方, 绿:下方）"""
    df['BBI'] = (df['close'].rolling(3).mean() +
                 df['close'].rolling(6).mean() +
                 df['close'].rolling(12).mean() +
                 df['close'].rolling(24).mean()) / 4
    df['BBI_Signal'] = np.where(df['close'] > df['BBI'], '红', '绿')
    return df


def calculate_zlmm(df):
    """主力买卖指标（红:主力净流入, 绿:净流出）"""
    df['MainNet'] = (df['close'] - df['open']) * df['volume']
    df['ZLMM_Signal'] = np.where(df['MainNet'] > 0, '红', '绿')
    return df


# ================== 策略逻辑模块 ==================
def six_sword_strategy(df):
    df = df.copy()
    df = (df.pipe(calculate_macd)
          .pipe(calculate_kdj)
          .pipe(calculate_rsi)
          .pipe(calculate_lwr)
          .pipe(calculate_bbi)
          .pipe(calculate_zlmm))

    # 买入条件：全部6指标为红
    buy_condition = (df['MACD_Signal'] == '红') & \
                    (df['KDJ_Signal'] == '红') & \
                    (df['RSI_Signal'] == '红') & \
                    (df['LWR_Signal'] == '红') & \
                    (df['BBI_Signal'] == '红') & \
                    (df['ZLMM_Signal'] == '红')

    # 卖出条件：任意3指标变绿
    signal_cols = ['MACD_Signal', 'KDJ_Signal', 'RSI_Signal',
                   'LWR_Signal', 'BBI_Signal', 'ZLMM_Signal']
    sell_condition = (df[signal_cols] == '绿').sum(axis=1) >= 3

    df['raw_buy'] = buy_condition.shift(1).fillna(False)
    df['raw_sell'] = sell_condition.shift(1).fillna(False)
    return df


def filter_signals(df):
    df = df.copy()
    df['clean_buy'] = False
    df['clean_sell'] = False
    hold_position = False

    for i in range(len(df)):
        if df.at[i, 'raw_buy'] and not hold_position:
            df.at[i, 'clean_buy'] = True
            hold_position = True
        if df.at[i, 'raw_sell'] and hold_position:
            df.at[i, 'clean_sell'] = True
            hold_position = False
    return df


# ================== 可视化模块 ==================
def plot_correct_kline(df):
    fig = go.Figure()

    # 修正K线颜色：涨红跌绿
    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing={
            'line': {'color': '#EF5350'},  # 上涨K线边框红色
            'fillcolor': '#EF5350'  # 上涨实体填充红色
        },
        decreasing={
            'line': {'color': '#26A69A'},  # 下跌K线边框绿色
            'fillcolor': '#26A69A'  # 下跌实体填充绿色
        },
        name='K线'
    ))

    # 买入信号标注（红色三角）
    buy_points = df[df['clean_buy']]
    if not buy_points.empty:
        fig.add_trace(go.Scatter(
            x=buy_points['date'],
            y=buy_points['low'] * 0.98,
            mode='markers',
            marker=dict(
                color='#D32F2F',
                size=12,
                symbol='triangle-up'
            ),
            name='买入信号'
        ))

    # 卖出信号标注（绿色三角）
    sell_points = df[df['clean_sell']]
    if not sell_points.empty:
        fig.add_trace(go.Scatter(
            x=sell_points['date'],
            y=sell_points['high'] * 1.02,
            mode='markers',
            marker=dict(
                color='#388E3C',
                size=12,
                symbol='triangle-down'
            ),
            name='卖出信号'
        ))

    fig.update_layout(
        title='六脉神剑策略',
        xaxis_rangeslider_visible=False,
        template='plotly_white',
        font=dict(family='Microsoft YaHei')  # 设置中文字体
    )
    st.plotly_chart(fig, use_container_width=True)


# ================== 数据获取模块 ==================
@st.cache_data
def get_stock_data(symbol, start, end):
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="hfq")
        df.reset_index(inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        st.error(f"数据获取失败: {str(e)}")
        return pd.DataFrame()


def app():
    #st.set_page_config(page_title="六脉神剑", layout="wide")
    st.title("🗡️ 六脉神剑策略系统")

    with st.sidebar:
        st.header("参数设置")
        symbol = st.text_input("股票代码", "sh600000")
        start_date = st.date_input("开始日期", datetime.now() - timedelta(days=90))
        end_date = st.date_input("结束日期", datetime.now())

    df = get_stock_data(symbol,
                        start_date.strftime("%Y%m%d"),
                        end_date.strftime("%Y%m%d"))
    if df.empty:
        st.stop()

    df = six_sword_strategy(df)
    df = filter_signals(df)

    st.subheader("K线图与交易信号")
    plot_correct_kline(df)

    col1, col2 = st.columns(2)
    col1.metric("买入信号次数", df['clean_buy'].sum())
    col2.metric("卖出信号次数", df['clean_sell'].sum())


if __name__ == "__main__":
    app()