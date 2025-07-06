import os
import pandas as pd
from mootdx.reader import Reader
import logging
import streamlit as st
import mplfinance as mpf
import matplotlib.pyplot as plt
from io import BytesIO
import sys

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通达信数据目录
TDX_PATH = '/mnt/c/new_tdx'

st.write("Streamlit version:", st.__version__)
st.write("Python executable:", sys.executable)

def get_stock_list():
    """
    只获取A股股票代码（sh600000、sz000001等），过滤掉指数、债券等。
    直接使用day文件名（去掉.day后缀），不再拼接market前缀。
    """
    code_set = set()
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(TDX_PATH, f'vipdoc/{market}/lday')
        if not os.path.exists(lday_dir):
            continue
        files = [f for f in os.listdir(lday_dir) if f.endswith('.day')]
        for f in files:
            fname = os.path.splitext(f)[0]  # 例如 sz000001
            if fname.startswith(('sh600', 'sh601', 'sh603', 'sh605', 'sh688',
                                 'sz000', 'sz001', 'sz002', 'sz003', 'sz300', 'sz301')):
                code_set.add(fname)
    return sorted(code_set)


def get_history_df(symbol):
    """
    读取某只股票的全部历史日线数据，返回DataFrame，date为index
    """
    if symbol.startswith('sh'):
        code = symbol[2:]
        market = 1
    elif symbol.startswith('sz'):
        code = symbol[2:]
        market = 0
    else:
        return None
    reader = Reader.factory(market='std', tdxdir=TDX_PATH)
    df = reader.daily(symbol=code, market=market)
    if df is None:
        return None
    if 'date' not in df.columns:
        if df.index.name == 'date':
            df = df.reset_index()
        else:
            return None
    # 保证date为datetime类型并设为index
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    return df


def main():
    st.title("A股120日新高股票筛选")
    reader = Reader.factory(market='std', tdxdir=TDX_PATH)
    stock_list = get_stock_list()
    logger.info(f"本地A股代码数: {len(stock_list)}")

    # 只处理前10只股票用于调试，后续可注释掉
    stock_list = stock_list[:10]

    results = []

    logger.info(f"开始处理 {len(stock_list)} 只股票...")
    progress_bar = st.progress(0)
    for idx, symbol in enumerate(stock_list, 1):
        try:
            # 剥离市场前缀
            if symbol.startswith('sh'):
                code = symbol[2:]
                market = 1  # 上交所
            elif symbol.startswith('sz'):
                code = symbol[2:]
                market = 0  # 深交所
            else:
                logger.debug(f"跳过未知市场代码: {symbol}")
                continue
            logger.debug(f"[{idx}/{len(stock_list)}] 处理 {symbol} ({code}) ...")
            df = reader.daily(symbol=code, market=market)
            if df is None:
                logger.info(f"{symbol} 无法读取数据，跳过")
                continue
            if 'date' not in df.columns:
                if df.index.name == 'date':
                    df = df.reset_index()
                else:
                    logger.info(f"{symbol} 数据缺少 date 字段，跳过")
                    logger.info(f"{symbol} DataFrame columns: {df.columns}, head: {df.head()}")
                    continue
            if len(df) < 120:
                logger.info(f"{symbol} 数据不足120天，仅有{len(df)}天，跳过120日新高判断，转为首日对比")
                # 新增逻辑：今日收盘价是否高于第一天收盘价
                last_close = df['close'].iloc[-1]
                first_close = df['close'].iloc[0]
                logger.debug(f"{symbol} 首日收盘价: {first_close}, 今日收盘价: {last_close}")
                if last_close > first_close:
                    logger.info(f"{symbol} 今日收盘价高于首日收盘价: {last_close} > {first_close}")
                    results.append({'code': symbol, 'date': df['date'].iloc[-1], 'close': last_close})
                progress_bar.progress(idx / len(stock_list))
                continue
            df['date'] = df['date'].astype(str)
            last_close = df['close'].iloc[-1]
            prev_120 = df['close'].iloc[-120:-1]
            logger.debug(f"{symbol} 最后收盘价: {last_close}, 过去119天最高: {prev_120.max()}")
            if last_close > prev_120.max():
                logger.info(f"{symbol} 创120日新高: {last_close} > {prev_120.max()}")
                results.append({'code': symbol, 'date': df['date'].iloc[-1], 'close': last_close})
            progress_bar.progress(idx / len(stock_list))
        except Exception as e:
            logger.warning(f"{symbol} 读取失败: {e}")
            progress_bar.progress(idx / len(stock_list))
    logger.info(f"处理完毕，符合条件的股票数量: {len(results)}")

    df_result = pd.DataFrame(results)
    if not df_result.empty and 'date' in df_result.columns:
        df_result['date'] = df_result['date'].astype(str)
    st.subheader(f"筛选结果（共{len(df_result)}只股票）")

    # 显示可交互表格，允许单行选择
    selected = st.data_editor(
        df_result,
        use_container_width=True,
        hide_index=True,
        column_order=("code", "date", "close"),
        key="stock_table",
        row_selection='single',  # 允许单行选择
        num_rows="dynamic"
    )

    # 检查是否有选中行
    if selected is not None and not selected.empty:
        selected_code = selected.iloc[0]["code"]
        st.write(f"{selected_code} 历史K线图：")
        hist_df = get_history_df(selected_code)
        if hist_df is not None and not hist_df.empty:
            hist_df_plot = hist_df.rename(columns={
                'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
            })
            fig, axlist = mpf.plot(hist_df_plot, type='candle', volume=True, style='yahoo', returnfig=True, figsize=(10, 6))
            st.pyplot(fig)
        else:
            st.warning("无法获取该股票历史数据或数据为空！")


if __name__ == "__main__":
    main()
