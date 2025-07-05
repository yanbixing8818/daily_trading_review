import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from mootdx.reader import Reader
import os
import talib
import streamlit as st
import mplfinance as mpf
import io
from PIL import Image
import matplotlib
import matplotlib.font_manager as fm
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

def get_chip_ratio(df, price_range=(0, 0.3), days=20):
    """
    计算最近days天收盘价在某价格区间的比例
    :param df: DataFrame，需有'close'列
    :param price_range: (low, high)，如(0,0.3)表示底部30%
    :param days: 统计区间长度
    :return: 比例（0~1）
    """
    if len(df) < days:
        return np.nan
    closes = df['close'].tail(days)
    min_p = closes.min()
    max_p = closes.max()
    if max_p == min_p:
        return 1.0  # 全部集中
    normed = (closes - min_p) / (max_p - min_p)
    ratio = ((normed >= price_range[0]) & (normed <= price_range[1])).sum() / days
    return ratio

def chip_stability(df, days=20):
    bottom_ratio = get_chip_ratio(df, price_range=(0, 0.3), days=days) #底部30%价格区间
    current_ratio = get_chip_ratio(df, price_range=(0.7, 1), days=days) #当前价格区间
    print(f"DEBUG chip_stability: bottom_ratio={bottom_ratio:.2f}, current_ratio={current_ratio:.2f}")
    return bottom_ratio > 0.65 and current_ratio < 0.21

def detect_wash_and_distribute(stock_code, tdx_dir='C:/new_tdx', days=10):
    """
    检测股票前N个交易日的洗盘和出货信号（使用本地通达信数据）
    :param stock_code: 股票代码 (如 '600000')
    :param tdx_dir: 通达信数据目录路径
    :param days: 分析天数
    :return: 包含洗盘和出货信号的字典
    """
    # 确保股票代码是6位数字格式
    stock_code = stock_code.zfill(6)
    
    # 初始化通达信数据读取器[1,2,4](@ref)
    reader = Reader.factory(market='std', tdxdir=tdx_dir)
    
    try:
        # 读取日线数据[1,2](@ref)
        df = reader.daily(symbol=stock_code)
        # 补齐date字段
        if 'date' not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.copy()
                df['date'] = df.index
            else:
                df = df.copy()
                df['date'] = pd.Series(
                    pd.date_range(end=pd.Timestamp.today(), periods=len(df))
                ).values

        # 兼容不同字段名，补齐vol字段
        if 'vol' not in df.columns:
            if 'volume' in df.columns:
                df['vol'] = df['volume']
            elif 'amount' in df.columns:
                df['vol'] = df['amount']
            else:
                raise ValueError("找不到成交量字段（vol/volume/amount）")

        # 关键：重置index，去掉index名，避免歧义
        df = df.reset_index(drop=True)
    except Exception as e:
        print(f"读取数据失败: {e}")
        return {'wash_dates': [], 'distribute_dates': []}, None
    
    # 检查是否成功读取数据
    if df.empty:
        print(f"未找到股票 {stock_code} 的日线数据")
        return {'wash_dates': [], 'distribute_dates': []}, None
    
    # 确保df按交易日升序
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    wash_dates = []
    distribute_dates = []

    # 只遍历最近days个交易日
    recent_dates = df['date'].iloc[-days:]

    for current_date in recent_dates:
        # 取当前日期及之前的历史数据
        hist = df[df['date'] <= current_date].copy()
        if len(hist) < 20:  # 技术指标最少20日
            continue
        # === 技术指标计算 ===
        hist['ma20'] = talib.MA(hist['close'], timeperiod=20)
        hist['ma5'] = talib.MA(hist['close'], timeperiod=5)
        hist['vol_ma5'] = talib.MA(hist['vol'], timeperiod=5)
        hist['vol_ma'] = hist['vol'].rolling(days).mean()
        row = hist.iloc[-1]  # 当天K线

        # === K线形态与成交量特征 ===
        lower_shadow = min(row['open'], row['close']) - row['low']  # 下影线长度
        body = abs(row['close'] - row['open'])  # 实体长度
        # cond1: 下影线较长（主力洗盘常见K线形态）
        cond1 = (lower_shadow > body * 1.4)
        # cond2: 缩量（成交量小于5日均量0.8倍，主力洗盘时常见缩量）
        cond2 = row['vol'] < row['vol_ma5'] * 0.8
        # cond3: 均线支撑（收盘价高于20日均线0.98倍，说明未有效跌破重要均线）
        cond3 = (row['close'] > row['ma20'] * 0.98) if not pd.isna(row['ma20']) else False
        # cond4: 缩量阴线/十字星（实体很短且缩量，主力不愿大幅砸盘）
        cond4 = (row['close'] <= row['open']) and (body < row['open'] * 0.01) and (row['vol'] < row['vol_ma'] * 0.8)

        # === 筹码集中度指标 ===
        # bottom_ratio: 近20日收盘价在底部30%区间的比例
        # current_ratio: 近20日收盘价在顶部30%区间的比例
        bottom_ratio = get_chip_ratio(hist, price_range=(0, 0.3), days=20)
        current_ratio = get_chip_ratio(hist, price_range=(0.7, 1), days=20)
        chip_ok = (bottom_ratio >= 0.65 and current_ratio <= 0.20)  # 筹码高度集中

        # === 洗盘信号判据 ===
        # 满足下影线+均线支撑，或缩量，或缩量阴线/十字星，且筹码集中
        wash_signal = ((cond1 and cond3) or cond2 or cond4) and chip_ok

        # === 出货信号判据 ===
        upper_shadow = row['high'] - max(row['open'], row['close'])  # 上影线长度
        # cond1d: 放量长上影线（高位出货常见形态）
        cond1d = (upper_shadow > body * 1.5) and (row['vol'] > row['vol_ma'] * 1.2)
        # cond2d: 高位放量阴线/十字星（主力借机出货）
        cond2d = (row['close'] < row['open']) and (body < row['open'] * 0.01) and (row['vol'] > row['vol_ma'] * 1.2)
        # cond3d: 均线破位（收盘价跌破20日均线0.97倍）
        cond3d = (row['close'] < row['ma20'] * 0.97) if not pd.isna(row['ma20']) else False
        # cond4d: 连续放量但涨幅有限（主力拉高出货，涨幅小但放量）
        cond4d = (row['vol'] > row['vol_ma'] * 1.5) and (abs((row['close'] - row['open']) / row['open']) < 0.01)
        # 只有筹码分散时才判为出货信号
        distribute_signal = (cond1d or cond2d or cond3d or cond4d) and (bottom_ratio < 0.5 or current_ratio > 0.25)

        # === debug log ===
        # print(f"DEBUG {row['date'].strftime('%Y-%m-%d')}: open={row['open']}, close={row['close']}, low={row['low']}, high={row['high']}, vol={row['vol']}, vol_ma5={row['vol_ma5']}, vol_ma={row['vol_ma']}, ma5={row['ma5']}, ma20={row['ma20']}, body={body}, lower_shadow={lower_shadow}, upper_shadow={upper_shadow}, wash_cond1={cond1}, wash_cond2={cond2}, wash_cond3={cond3}, wash_cond4={cond4}, bottom_ratio={bottom_ratio:.2f}, current_ratio={current_ratio:.2f}, chip_ok={chip_ok}, wash_signal={wash_signal}, dist_cond1={cond1d}, dist_cond2={cond2d}, dist_cond3={cond3d}, dist_cond4={cond4d}, distribute_signal={distribute_signal}")

        # === 信号收集 ===
        if wash_signal:
            wash_dates.append(row['date'].strftime('%Y-%m-%d'))
        if distribute_signal:
            distribute_dates.append(row['date'].strftime('%Y-%m-%d'))

    return {'wash_dates': wash_dates, 'distribute_dates': distribute_dates}, df

# Streamlit界面
st.title('洗盘/出货信号检测')

stock_code = st.text_input('请输入股票代码（如301176）:')

# 增加按钮，只有点击后才计算
if st.button('检测信号') and stock_code:
    tdx_dir = '/mnt/c/new_tdx'
    signals, df = detect_wash_and_distribute(stock_code, tdx_dir=tdx_dir, days=15)
    st.write(f"股票 {stock_code} 检测结果：")
    st.write(f"洗盘信号日期: {signals['wash_dates']}")
    st.write(f"出货信号日期: {signals['distribute_dates']}")
    st.table({
        '洗盘信号日期': signals['wash_dates'],
        '出货信号日期': signals['distribute_dates']
    })

    # 标注信号
    apds = []
    # 只显示最近20天
    df_plot = df.tail(20).copy()
    # 洗盘信号
    wash_y = pd.Series(np.nan, index=df_plot.index)
    if signals['wash_dates']:
        wash_mask = df_plot['date'].dt.strftime('%Y-%m-%d').isin(signals['wash_dates'])
        wash_y[wash_mask] = df_plot.loc[wash_mask, 'low'] * 0.98
        apds.append(mpf.make_addplot(wash_y, type='scatter', markersize=100, marker='^', color='blue'))
    # 出货信号
    dist_y = pd.Series(np.nan, index=df_plot.index)
    if signals['distribute_dates']:
        dist_mask = df_plot['date'].dt.strftime('%Y-%m-%d').isin(signals['distribute_dates'])
        dist_y[dist_mask] = df_plot.loc[dist_mask, 'high'] * 1.02
        apds.append(mpf.make_addplot(dist_y, type='scatter', markersize=100, marker='v', color='red'))

    # 绘制K线图到内存
    fig, axlist = mpf.plot(
        df_plot.set_index('date'),
        type='candle',
        mav=(5, 10, 20),
        addplot=apds if apds else None,
        returnfig=True,
        figsize=(10, 6),
        title=f"{stock_code} K线及信号"
    )
    # 在图片左上角添加图例说明
    legend_text = (
        "图例说明：\n"
        "蓝线：5日均线\n"
        "橙线：10日均线\n"
        "紫线：20日均线\n"
        "蓝色上三角：洗盘信号\n"
        "红色下三角：出货信号"
    )
    fig.text(0.01, 0.99, legend_text, fontsize=12, color='black', ha='left', va='top', linespacing=1.5, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    st.image(buf, caption=f"{stock_code} K线及信号")