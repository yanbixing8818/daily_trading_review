import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import talib
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# 全局设置
CHINESE_FONT = {'family': 'SimHei', 'size': 14}
PERIOD_MAP = {"日线": "daily", "周线": "weekly", "月线": "monthly"}








# 缓存数据获取
def get_stock_data(_symbol, start, end, period_type):
    try:
        df = ak.stock_zh_a_hist(
            symbol=_symbol,
            period=period_type,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq"
        )
        if df.empty:
            return pd.DataFrame()
        df['日期'] = pd.to_datetime(df['日期'])
        return df.sort_values('日期').set_index('日期')
    except Exception as e:
        st.error(f"数据获取失败: {str(e)}")
        return pd.DataFrame()


# 技术指标计算
def calculate_indicators(df):
    # 均线系统
    df['MA5'] = talib.SMA(df['收盘'], timeperiod=5)
    df['MA10'] = talib.SMA(df['收盘'], timeperiod=10)
    df['MA20'] = talib.SMA(df['收盘'], timeperiod=20)

    # MACD
    df['MACD'], df['MACDsignal'], df['MACDhist'] = talib.MACD(
        df['收盘'], fastperiod=12, slowperiod=26, signalperiod=9)

    # RSI
    df['RSI14'] = talib.RSI(df['收盘'], timeperiod=14)

    # KDJ
    df['slowk'], df['slowd'] = talib.STOCH(
        df['最高'], df['最低'], df['收盘'],
        fastk_period=9, slowk_period=3, slowk_matype=0,
        slowd_period=3, slowd_matype=0
    )
    df['slowj'] = 3 * df['slowk'] - 2 * df['slowd']

    # 布林带
    df['upper'], df['middle'], df['lower'] = talib.BBANDS(df['收盘'], timeperiod=20)

    # 成交量
    df['VOL_MA5'] = talib.SMA(df['成交量'], timeperiod=5)
    return df.dropna()


# 创建交互图表
def create_plotly_chart(df, period):
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.15, 0.2],
        specs=[[{"secondary_y": True}], [{}], [{}], [{}], [{}]]
    )

    # K线图（红涨绿跌）
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['开盘'],
        high=df['最高'],
        low=df['最低'],
        close=df['收盘'],
        name='K线',
        increasing={'line': {'color': 'red'}, 'fillcolor': 'rgba(255,0,0,0.3)'},
        decreasing={'line': {'color': 'green'}, 'fillcolor': 'rgba(0,128,0,0.3)'}
    ), row=1, col=1)

    # 均线系统
    for ma, color in zip(['MA5', 'MA10', 'MA20'], ['orange', 'blue', 'purple']):
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma],
            name=ma,
            line=dict(color=color, width=1.5),
            opacity=0.8
        ), row=1, col=1)

    # MACD
    colors = np.where(df['MACDhist'] > 0, 'red', 'green')
    fig.add_trace(go.Bar(
        x=df.index, y=df['MACDhist'],
        name='MACD Hist',
        marker_color=colors
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD'],
        line=dict(color='blue'),
        name='MACD'
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACDsignal'],
        line=dict(color='orange'),
        name='Signal'
    ), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI14'],
        line=dict(color='purple'),
        name='RSI 14'
    ), row=3, col=1)
    fig.add_hline(y=30, line=dict(color='gray', dash='dash'), row=3, col=1)
    fig.add_hline(y=70, line=dict(color='gray', dash='dash'), row=3, col=1)

    # KDJ
    fig.add_trace(go.Scatter(
        x=df.index, y=df['slowk'],
        line=dict(color='blue'),
        name='K值'
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['slowd'],
        line=dict(color='orange'),
        name='D值'
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['slowj'],
        line=dict(color='green', dash='dot'),
        name='J值'
    ), row=4, col=1)
    fig.add_hline(y=20, line=dict(color='gray', dash='dash'), row=4, col=1)
    fig.add_hline(y=80, line=dict(color='gray', dash='dash'), row=4, col=1)

    # 成交量
    colors = np.where(df['收盘'] > df['开盘'], 'red', 'green')
    fig.add_trace(go.Bar(
        x=df.index, y=df['成交量'],
        name='成交量',
        marker_color=colors,
        opacity=0.7
    ), row=5, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['VOL_MA5'],
        line=dict(color='orange'),
        name='成交量MA5'
    ), row=5, col=1)

    # 布局设置
    fig.update_layout(
        height=1200,
        title=f'{symbol} {period}级别技术分析',
        font=CHINESE_FONT,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode="x unified"
    )

    # Y轴标签
    yaxis_labels = ["价格", "MACD", "RSI", "KDJ", "成交量"]
    for i, label in enumerate(yaxis_labels, 1):
        fig.update_yaxes(title_text=label, row=i, col=1)

    return fig


# 主程序
def app():
    st.title("股票技术指标分析系统")

    symbol = st.text_input("股票代码（例如：600519）", "600519")
    start_date = st.date_input("开始日期", datetime.now() - timedelta(days=365))
    end_date = st.date_input("结束日期", datetime.now())
    period = st.radio("分析周期", ["日线"])
    # period = st.radio("分析周期", ["日线", "周线", "月线"])
    analyze_clicked = st.button("开始分析", type="primary", help="点击后开始获取数据并分析")
    st.markdown("---")

    if analyze_clicked:
        with st.spinner('数据加载中，请稍候...'):
            df = get_stock_data(
                _symbol=symbol,
                start=start_date,
                end=end_date,
                period_type=PERIOD_MAP[period]
            )

            if df.empty:
                st.warning("未获取到有效数据，请检查股票代码是否正确")
                return

            df = calculate_indicators(df)
            latest = df.iloc[-1]

        # 技术状态面板
        with st.container():
            st.subheader("📌 实时技术状态")
            cols = st.columns(6)

            # 均线排列
            ma_condition = (latest['MA5'] > latest['MA10']) & (latest['MA10'] > latest['MA20'])
            cols[0].metric("均线排列", "多头" if ma_condition else "空头",
                           delta="↑↑↑" if ma_condition else "↓↓↓",
                           help="MA5 > MA10 > MA20 为多头排列")

            # MACD
            macd_cross = latest['MACD'] > latest['MACDsignal']
            cols[1].metric("MACD", "金叉" if macd_cross else "死叉",
                           delta_color="off",
                           help="MACD线上穿信号线为金叉，反之为死叉")

            # RSI
            rsi_status = "超买" if latest['RSI14'] > 70 else "超卖" if latest['RSI14'] < 30 else "正常"
            cols[2].metric("RSI(14)", f"{latest['RSI14']:.1f}", rsi_status,
                           help=">70超买，<30超卖")

            # KDJ
            kdj_status = []
            if latest['slowk'] > 80 or latest['slowd'] > 80:
                kdj_status.append("超买")
            if latest['slowk'] < 20 or latest['slowd'] < 20:
                kdj_status.append("超卖")
            kdj_status = "/".join(kdj_status) if kdj_status else "正常"

            cross_status = ""
            if latest['slowk'] > latest['slowd'] and df['slowk'].iloc[-2] <= df['slowd'].iloc[-2]:
                cross_status = "金叉↑"
            elif latest['slowk'] < latest['slowd'] and df['slowk'].iloc[-2] >= df['slowd'].iloc[-2]:
                cross_status = "死叉↓"

            cols[3].metric("KDJ", f"K:{latest['slowk']:.1f}/D:{latest['slowd']:.1f}",
                           f"{kdj_status} {cross_status}",
                           help="K/D>80超买，<20超卖，金叉看涨")

            # 成交量
            vol_break = latest['成交量'] > latest['VOL_MA5'] * 1.2
            cols[4].metric("成交量",
                           f"{latest['成交量'] / 10000:.1f}万手",
                           "放量↑" if vol_break else "平量",
                           help="突破5日均量20%为有效放量")

            # 价格位置
            price_rank = (latest['收盘'] - df['收盘'].rolling(60).min().iloc[-1]) / \
                         (df['收盘'].rolling(60).max().iloc[-1] - df['收盘'].rolling(60).min().iloc[-1])
            cols[5].metric("价格位置", f"{price_rank * 100:.1f}%",
                           "高位" if price_rank > 0.7 else "低位" if price_rank < 0.3 else "中位",
                           help="当前价格在60日区间中的位置")

        # 显示图表
        st.plotly_chart(create_plotly_chart(df, period), use_container_width=True)

        # 指标说明
        with st.expander("📚 技术指标详解", expanded=True):
            st.markdown("""
            ### 核心指标解析
            ​**均线系统**  
            - 多头排列（MA5>MA10>MA20）预示上升趋势  
            - 价格在MA5上方为短期强势  

            ​**MACD指标**  
            - 金叉（蓝线上穿橙线）为买入信号  
            - 红柱扩大表示多头动能增强  

            ​**RSI指标**  
            - 70以上超买区警惕回调  
            - 30以下超卖区关注反弹  

            ​**KDJ指标**  
            - K/D值超过80为超买，低于20为超卖  
            - J值反应最灵敏，超过100为极端超买  

            ​**成交量分析**  
            - 放量突破均量为有效信号  
            - 量价背离可能预示趋势反转  
            """)

    else:
        st.info("✅ 请在左侧输入参数后点击【开始分析】按钮")


if __name__ == "__main__":
    app()