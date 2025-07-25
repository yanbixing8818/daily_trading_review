import baostock as bs
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler
import datetime
import matplotlib.pyplot as plt
import os
from mootdx.reader import Reader
import glob
import talib
import joblib
import matplotlib
import baostock as bs
from mootdx.affair import Affair
import csv
from sklearn.impute import SimpleImputer
import pickle
import lightgbm as lgb
from sklearn.metrics import roc_auc_score

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
from sklearn.model_selection import TimeSeriesSplit

# 通达信数据目录（请根据实际情况修改）
TDX_PATH = '/mnt/c/new_tdx'
# 统一base_data目录
BASE_DATA_DIR = 'base_data'
os.makedirs(BASE_DATA_DIR, exist_ok=True)
# 统一模型目录
MODELS_DIR = 'models'
os.makedirs(MODELS_DIR, exist_ok=True)

def get_stock_name_mapping():
    """使用baostock获取A股代码和名称的映射，带本地缓存"""
    cache_file = os.path.join(BASE_DATA_DIR, 'stock_name_mapping.csv')
    if os.path.exists(cache_file):
        print(f"从缓存文件 {cache_file} 加载股票名称映射。")
        return pd.read_csv(cache_file)

    print("从baostock接口获取股票名称映射...")
    bs.login()
    rs = bs.query_stock_basic()
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    result = pd.DataFrame(data_list, columns=rs.fields)
    bs.logout()
    # baostock的ts_code是sh.600000, 我们的格式是sh600000
    result['ts_code'] = result['code'].str.replace('.', '', regex=False)
    name_map = result[['ts_code', 'code_name']].rename(columns={'code_name': 'name'})
    
    # 保存到缓存文件
    name_map.to_csv(cache_file, index=False, encoding='utf-8-sig')
    print(f"股票名称映射已缓存到 {cache_file}。")
    return name_map

def get_outstanding_map_from_tdx(tdx_path, csv_path=None, zip_filename=None):
    """
    从本地通达信财务数据（gpcw*.zip）提取所有A股流通股本，保存为csv，并返回dict。
    :param tdx_path: 通达信目录
    :param csv_path: 输出csv路径
    :param zip_filename: 财务zip文件名（如gpcw20241231.zip），默认自动查找最新
    :return: {code: outstanding}
    """
    if csv_path is None:
        csv_path = os.path.join(BASE_DATA_DIR, 'outstanding_map.csv')
    if os.path.exists(csv_path):
        df_out = pd.read_csv(csv_path, dtype={'code': str})
        if 'code' in df_out.columns and 'outstanding' in df_out.columns:
            return dict(zip(df_out['code'], df_out['outstanding']))
        elif 'symbol' in df_out.columns and 'outstanding' in df_out.columns:
            return dict(zip(df_out['symbol'], df_out['outstanding']))
        else:
            print(f"警告：{csv_path} 文件格式异常，将重新生成。")
            os.remove(csv_path)
    tmp_dir = os.path.join(tdx_path, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    affair_reader = Affair()
    # 如果未指定zip文件，则尝试下载所有财务文件；否则假定文件已存在
    if zip_filename is None:
        print("未指定财务zip文件，尝试自动下载和查找...")
        affair_reader.fetch(downdir=tmp_dir)
        files = [f for f in os.listdir(tmp_dir) if f.startswith('gpcw') and f.endswith('.zip')]
        if not files:
            raise FileNotFoundError('在tmp目录未找到gpcw*.zip财务文件')
        zip_filename = sorted(files)[-1]
    print("选用zip文件：", zip_filename)
    # 检查指定文件是否存在
    if not os.path.exists(os.path.join(tmp_dir, zip_filename)):
        raise FileNotFoundError(f"指定的财务文件 {zip_filename} 在 {tmp_dir} 中不存在。")
    # 解析zip
    data = affair_reader.parse(downdir=tmp_dir, filename=zip_filename)
    out_rows = []
    for code in data.index:
        row = data.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        outstanding = None
        val = row.get('已上市流通A股')
        if '已上市流通A股' in data.columns and pd.notna(val):
            outstanding = val
        else:
            val = row.get('自由流通股(股)')
            if '自由流通股(股)' in data.columns and pd.notna(val):
                outstanding = val
            else:
                val = row.get('总股本')
                if '总股本' in data.columns and pd.notna(val):
                    outstanding = val
        if outstanding is not None:
            out_rows.append({'code': str(code).zfill(6), 'outstanding': outstanding})
    df_out = pd.DataFrame(out_rows)
    if df_out.empty:
        raise RuntimeError("未能获取任何流通股本数据，请检查通达信财务数据文件内容或字段名。")
    df_out['code'] = df_out['code'].astype(str).str.zfill(6)
    df_out.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)
    return dict(zip(df_out['code'], df_out['outstanding']))

OUTSTANDING_MAP = get_outstanding_map_from_tdx(
    tdx_path=TDX_PATH,
    csv_path=os.path.join(BASE_DATA_DIR, 'outstanding_map.csv'),
    zip_filename='gpcw20250331.zip'
)

# 获取本地A股代码列表
def get_stock_list():
    code_set = set()
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(TDX_PATH, f'vipdoc/{market}/lday')
        if not os.path.exists(lday_dir):
            continue
        files = glob.glob(os.path.join(lday_dir, '*.day'))
        for f in files:
            fname = os.path.splitext(os.path.basename(f))[0]
            if (fname.startswith('sh') or fname.startswith('sz')) and fname[2:].isdigit():
                code = fname[2:]
                # 只保留部分板块（可根据需要调整）
                #if code.startswith(('600', '601', '603', '605', '688', '000', '001', '002', '003', '300', '301', '83', '87')):
                if code.startswith(('300', '301')):
                    code_set.add(fname)
    code_list = sorted(code_set)
    return code_list

def get_local_data(symbol, days=800):
    try:
        reader = Reader.factory(market='std', tdxdir=TDX_PATH)
        daily_data = reader.daily(symbol=symbol)
        if daily_data is None or len(daily_data) < days:
            return None
        if 'date' not in daily_data.columns:
            if hasattr(daily_data.index, 'to_timestamp') or isinstance(daily_data.index, pd.DatetimeIndex):
                daily_data = daily_data.copy()
                daily_data['date'] = daily_data.index.strftime('%Y%m%d')
            else:
                daily_data = daily_data.copy()
                daily_data['date'] = pd.Series(
                    pd.date_range(end=pd.Timestamp.today(), periods=len(daily_data))
                ).dt.strftime('%Y%m%d').values
        else:
            daily_data['date'] = daily_data['date'].dt.strftime('%Y%m%d')
        daily_data['ts_code'] = symbol
        return daily_data.tail(days)
    except Exception as e:
        print(f"获取{symbol}数据失败: {str(e)}")
        return None

def filter_st_stocks(stock_df, st_file='st_stocks.xlsx'):
    """根据st_stocks.xlsx文件剔除ST股票"""
    st_path = os.path.join(BASE_DATA_DIR, st_file)
    if not os.path.exists(st_path):
        print(f"警告：未找到ST股票文件 {st_path}，不进行剔除。")
        return stock_df

    st_df = pd.read_excel(st_path)
    # 兼容列名
    code_col = None
    for col in st_df.columns:
        if col.lower() in ['ts_code', '股票代码']:
            code_col = col
            break
    if code_col is None:
        raise ValueError(f'{st_file} 必须包含 ts_code 或 股票代码 列')

    # 转换格式 603268.SH -> sh603268
    def convert_code(code):
        code = str(code)
        if code.endswith('.SH'):
            return 'sh' + code[:6]
        elif code.endswith('.SZ'):
            return 'sz' + code[:6]
        else:
            return code.lower()

    st_codes = set(st_df[code_col].map(convert_code))
    before = len(stock_df)
    filtered_df = stock_df[~stock_df['ts_code'].astype(str).isin(st_codes)]
    after = len(filtered_df)
    print(f"已根据{st_file}剔除ST股票，剩余: {after}，剔除: {before-after}")
    return filtered_df

# 筹码相关
def get_chip_ratio(close_series, price_range=(0, 0.3), days=20):
    if len(close_series) < days:
        return np.nan
    closes = close_series[-days:]
    min_p = closes.min()
    max_p = closes.max()
    if max_p == min_p:
        return 1.0
    normed = (closes - min_p) / (max_p - min_p)
    ratio = ((normed >= price_range[0]) & (normed <= price_range[1])).sum() / days
    return ratio

# 筹码稳定度计算公式
def chip_stability(close_series, days=20):
    bottom_ratio = get_chip_ratio(close_series, price_range=(0, 0.3), days=days)
    current_ratio = get_chip_ratio(close_series, price_range=(0.7, 1), days=days)
    return int(bottom_ratio > 0.65 and current_ratio < 0.21)

# 统一因子开关配置
FACTOR_SWITCHES = {
    'DDE_NET_LARGE_ORDER_VOLUME': True,
    'PCT_CHG': True,
    'AMPLITUDE': True,
    'NEW_HIGH': True,
    'RSI': True,
    'MACD_CROSS': True,
    'BBI': True,
    # 如需添加更多因子，继续补充
}

def add_sentiment_features(df):
    """添加市场情绪特征"""
    # 先确保有is_zhangting列
    if 'is_zhangting' not in df.columns:
        # 动态生成is_zhangting列
        df['is_zhangting'] = df.apply(lambda row: is_zhangting(row), axis=1)
    # 涨停家数占比
    df['zt_ratio'] = df.groupby('date')['is_zhangting'].transform('mean')
    # 连板高度（近5日内连续涨停天数，0为非连板，1为1板，2为2连板...）
    def calc_lianban_height(s):
        cnt = 0
        for v in reversed(s):
            if v:
                cnt += 1
            else:
                break
        return cnt
    df['lianban_height'] = df.groupby('ts_code')['is_zhangting'].transform(lambda x: x.rolling(5, min_periods=1).apply(calc_lianban_height, raw=True))
    return df

def calculate_technical_features(df, high_window=60, vol_window=20, ma_window=60, vol_ratio=1.5, factor_switches=None):
    """预处理数据，并计算所有技术指标和形态特征"""
    if factor_switches is None:
        factor_switches = {}
    # --- Preprocessing ---
    df = df.replace(['--', 'NaN', 'NA'], np.nan)
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=numeric_cols) # 只在关键数值列上dropna
    
    # --- Derived Features ---
    if 'close' in df.columns and 'volume' in df.columns:
        df['市值'] = df['close'] * df['volume']
        df['市值_log'] = np.log(df['市值'] + 1)
        df['量价比'] = df['volume'] / (df['close'].abs() + 0.01)
        
    # --- Standard Technical Indicators (TA-Lib) ---
    df = df.copy()
    for code, group in df.groupby('ts_code'):
        idx = group.index
        # 获取流通股本并计算换手率
        code6 = code[2:] if code.startswith(('sh', 'sz')) else code
        outstanding = OUTSTANDING_MAP.get(code6, np.nan)
        if outstanding and 'volume' in group.columns:
            df.loc[idx, 'turnover_rate'] = group['volume'] / outstanding
        else:
            df.loc[idx, 'turnover_rate'] = np.nan
        
        # 量比 = 当日成交量 / (前5日平均成交量)   ！！！！！！！！这里需要考虑涨停板对于量能的影响情况！！！！！！！
        if 'volume' in group.columns and len(group) > 5:
            avg_5d_vol = pd.Series(group['volume']).rolling(5).mean()
            df.loc[idx, 'volume_ratio'] = group['volume'] / (avg_5d_vol)
        else:
            df.loc[idx, 'volume_ratio'] = np.nan
        
        # DDE大单净量
        if factor_switches.get('DDE_NET_LARGE_ORDER_VOLUME', False):
            try:
                minute_reader = Reader.factory(market='std', tdxdir=TDX_PATH)
                min1_df = minute_reader.minute(symbol=code)
                if min1_df is not None and not min1_df.empty:
                    if isinstance(min1_df.index, pd.DatetimeIndex):
                        min1_df = min1_df.copy()
                        min1_df['date'] = min1_df.index.strftime('%Y%m%d')
                    for i, row in group.iterrows():
                        cur_date = str(row['date'])
                        day_min1 = min1_df[min1_df['date'] == cur_date]
                        large_orders = day_min1[day_min1['amount'] >= 5000000]
                        buy_vol = large_orders[large_orders['close'] > large_orders['open']]['volume'].sum()
                        sell_vol = large_orders[large_orders['close'] < large_orders['open']]['volume'].sum()
                        if outstanding and outstanding > 0:
                            dde_value = (buy_vol - sell_vol) / outstanding * 100
                            df.at[i, 'dde_net_large_order_volume'] = dde_value
                        else:
                            df.at[i, 'dde_net_large_order_volume'] = np.nan
                        # 新增主力强度指标
                        df.at[i, 'main_strength'] = (buy_vol - sell_vol) / (buy_vol + sell_vol + 1e-6)
                else:
                    df.loc[idx, 'dde_net_large_order_volume'] = np.nan
                    df.loc[idx, 'main_strength'] = np.nan
            except Exception as e:
                df.loc[idx, 'dde_net_large_order_volume'] = np.nan
                df.loc[idx, 'main_strength'] = np.nan
        else:
            df.loc[idx, 'dde_net_large_order_volume'] = np.nan
            df.loc[idx, 'main_strength'] = np.nan

        close = group['close'].values
        volume = group['volume'].values if 'volume' in group.columns else None
        # 均线
        df.loc[idx, 'ma5'] = talib.MA(close, timeperiod=5)
        df.loc[idx, 'ma10'] = talib.MA(close, timeperiod=10)
        df.loc[idx, 'ma20'] = talib.MA(close, timeperiod=20)
        df.loc[idx, 'ma60'] = talib.MA(close, timeperiod=ma_window)
        
        # MACD
        macd, macdsignal, _ = talib.MACD(close)
        df.loc[idx, 'macd'] = macd
        df.loc[idx, 'signal'] = macdsignal
        # MACD金叉/死叉信号
        golden_cross = ((pd.Series(macd).shift(1) < pd.Series(macdsignal).shift(1)) & (macd >= macdsignal)).astype(int)
        dead_cross = ((pd.Series(macd).shift(1) > pd.Series(macdsignal).shift(1)) & (macd <= macdsignal)).astype(int)
        df.loc[idx, 'macd_golden_cross_signal'] = golden_cross
        df.loc[idx, 'macd_dead_cross_signal'] = dead_cross
        # 金叉区间信号：金叉后到死叉前都为1
        zone = np.zeros_like(macd, dtype=int)
        in_zone = False
        for i in range(len(macd)):
            if golden_cross.iloc[i]:
                in_zone = True
            if dead_cross.iloc[i]:
                in_zone = False
            zone[i] = int(in_zone)
        df.loc[idx, 'macd_golden_cross_zone'] = zone
        
        # RSI
        # 新增RSI6、RSI12及其比较因子
        if factor_switches.get('RSI', True):
            df.loc[idx, 'RSI_6'] = talib.RSI(close, timeperiod=6)
            df.loc[idx, 'RSI_12'] = talib.RSI(close, timeperiod=12)
            df.loc[idx, 'rsi6_ge_rsi12'] = (df.loc[idx, 'RSI_6'] >= df.loc[idx, 'RSI_12']).astype(int)
        else:
            df.loc[idx, 'RSI_6'] = np.nan
            df.loc[idx, 'RSI_12'] = np.nan
            df.loc[idx, 'rsi6_ge_rsi12'] = np.nan
        
        # 布林带
        upper, middle, lower = talib.BBANDS(close, timeperiod=20)
        df.loc[idx, 'boll_upper'] = upper
        df.loc[idx, 'boll_mid'] = middle
        df.loc[idx, 'boll_lower'] = lower
        
        # BBI（多空分界线）
        if factor_switches.get('BBI', True):
            bbi = (talib.MA(close, 5) + talib.MA(close, 10) + talib.MA(close, 20) + talib.MA(close, 40)) / 4
            df.loc[idx, 'BBI5'] = bbi
        else:
            df.loc[idx, 'BBI5'] = np.nan
        
        # 筹码相关
        close_series = pd.Series(close)
        df.loc[idx, 'chip_bottom_ratio_20d'] = close_series.rolling(20).apply(lambda x: get_chip_ratio(x, price_range=(0, 0.3), days=20), raw=False).values
        df.loc[idx, 'chip_top_ratio_20d'] = close_series.rolling(20).apply(lambda x: get_chip_ratio(x, price_range=(0.7, 1), days=20), raw=False).values
        df.loc[idx, 'chip_stability_20d'] = close_series.rolling(20).apply(lambda x: chip_stability(x, days=20), raw=False).values
        
        # 滞后特征
        for i in range(1, 4):
            df.loc[idx, f'close_lag{i}'] = pd.Series(close).shift(i).values
            if volume is not None:
                df.loc[idx, f'volume_lag{i}'] = pd.Series(volume).shift(i).values
        
        # 新增：3日、5日、10日涨幅
        if factor_switches.get('PCT_CHG', True):
            df.loc[idx, 'pct_chg_3d'] = pd.Series(close).pct_change(3).values
            df.loc[idx, 'pct_chg_5d'] = pd.Series(close).pct_change(5).values
            df.loc[idx, 'pct_chg_10d'] = pd.Series(close).pct_change(10).values
        else:
            df.loc[idx, 'pct_chg_3d'] = np.nan
            df.loc[idx, 'pct_chg_5d'] = np.nan
            df.loc[idx, 'pct_chg_10d'] = np.nan
            
        # 新增：3日、5日、10日震荡因子（振幅）
        if factor_switches.get('AMPLITUDE', True):
            df.loc[idx, 'amplitude_3d'] = (group['high'].rolling(3).max() - group['low'].rolling(3).min()) / group['low'].rolling(3).min()
            df.loc[idx, 'amplitude_5d'] = (group['high'].rolling(5).max() - group['low'].rolling(5).min()) / group['low'].rolling(5).min()
            df.loc[idx, 'amplitude_10d'] = (group['high'].rolling(10).max() - group['low'].rolling(10).min()) / group['low'].rolling(10).min()
        else:
            df.loc[idx, 'amplitude_3d'] = np.nan
            df.loc[idx, 'amplitude_5d'] = np.nan
            df.loc[idx, 'amplitude_10d'] = np.nan

    # 2. 形态信号特征 (在所有基础指标计算后进行)
    # 新高
    
    # 新增：10日新高因子
    if factor_switches.get('NEW_HIGH', True):
        df['is_new_high'] = (df['close'] == df.groupby('ts_code')['close'].transform(lambda x: x.rolling(high_window, min_periods=1).max())).astype(int)
        df['is_new_high_10d'] = (df['close'] == df.groupby('ts_code')['close'].transform(lambda x: x.rolling(10, min_periods=1).max())).astype(int)
    else:
        df['is_new_high'] = np.nan
        df['is_new_high_10d'] = np.nan
    # 均线多头排列
    df['multi_ma'] = ((df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20']) & (df['ma20'] > df['ma60'])).astype(int)
    # 放量突破60日线
    df['ma60_cross'] = ((df['close'] > df['ma60']) & (df.groupby('ts_code')['close'].shift(1) <= df.groupby('ts_code')['ma60'].shift(1))).astype(int)
    df['vol_ma20'] = df.groupby('ts_code')['volume'].transform(lambda x: x.rolling(vol_window).mean())
    df['vol_break'] = (df['volume'] > df['vol_ma20'] * vol_ratio).astype(int)
    
    # 添加市场情绪特征
    df = add_sentiment_features(df)
    return df

def is_zhangting(row, limit_rate=0.2, tol=0.003):
    """
    判断某一行日线数据是否涨停，排除一字涨停，允许一定容差。
    """
    if 'close' not in row or 'pre_close' not in row or 'open' not in row:
        return False
    if pd.isna(row['close']) or pd.isna(row['pre_close']) or pd.isna(row['open']):
        return False
    zt_price = row['pre_close'] * (1 + limit_rate)
    # 涨停且不是一字涨停（开盘价!=收盘价），允许一定容差
    return (row['close'] >= zt_price - tol) and not (abs(row['open'] - row['close']) < 1e-6 and abs(row['open'] - zt_price) < 1e-6)

def create_target(df, next_day_thresh=0.1, neg_weight=10.0, zhangting_weight=10.0, chonggao_weight=10.0):
    """只创建目标标签和样本权重，涨停样本赋予更高权重，冲高回落样本也赋予高权重"""
    df = df.copy()
    # 明日收盘涨跌幅
    df['next_day_return'] = df.groupby('ts_code')['close'].transform(lambda x: x.shift(-1) / x - 1)
    # 明日开盘涨跌幅
    df['next_day_open_return'] = df.groupby('ts_code')['open'].transform(lambda x: x.shift(-1) / x - 1)
    # 明日收盘涨跌幅（已算）
    df['target'] = (df['next_day_return'] >= next_day_thresh).astype(int)
    df['sample_weight'] = 5.0
    # 1. 跌幅>7%高权重
    df.loc[df['next_day_return'] <= -0.07, 'sample_weight'] = neg_weight
    # 2. 冲高回落高权重（如盘中回落超10%）
    df['next_day_high_return'] = df.groupby('ts_code')['high'].transform(lambda x: x.shift(-1) / x - 1)
    chonggao_mask = (df['next_day_high_return'] - df['next_day_return'] >= 0.10)
    df.loc[chonggao_mask, 'sample_weight'] = chonggao_weight
    # 3. 涨停高权重
    if 'close' in df.columns and 'pre_close' in df.columns:
        is_zt = df.apply(lambda row: is_zhangting(row), axis=1)
        df.loc[is_zt, 'sample_weight'] = zhangting_weight
    return df

def feature_selection(df):
    features = [
        'open', 'high', 'low', 'close', 'volume', 'amount',
        '市值', '市值_log', '量价比',
        'ma5', 'ma10', 'ma20', 'ma60', 'macd', 'signal',
        'RSI_6', 'RSI_12', 'rsi6_ge_rsi12',
        'macd_golden_cross_zone',  # 只保留金叉区间信号
        'BBI5',
        'boll_mid', 'boll_upper', 'boll_lower',
        'chip_bottom_ratio_20d', 'chip_top_ratio_20d', 'chip_stability_20d',
        'pct_chg_3d', 'pct_chg_5d', 'pct_chg_10d',
        'amplitude_3d', 'amplitude_5d', 'amplitude_10d',
        'close_lag1', 'close_lag2', 'close_lag3',
        'volume_lag1', 'volume_lag2', 'volume_lag3',
        # 新增的形态特征
        'is_new_high', 'is_new_high_10d', 'multi_ma', 'ma60_cross', 'vol_break',
        # 新增换手率
        'turnover_rate',
        # 新增DDE大单净量
        'dde_net_large_order_volume',
        'main_strength',
        # 新增市场情绪特征
        'zt_ratio', 'lianban_height'
    ]
    features = [f for f in features if f in df.columns]
    return features

def train_xgb(X, y, features, sample_weight, model_path=None, scaler_path=None):
    """加载或训练XGBoost模型"""
    if model_path is None:
        model_path = os.path.join(MODELS_DIR, 'xgb_model.json')
    if scaler_path is None:
        scaler_path = os.path.join(MODELS_DIR, 'xgb_scaler.pkl')
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        print('已加载XGBoost模型和scaler')
        xgb_model = xgb.Booster()
        xgb_model.load_model(model_path)
        xgb_scaler = joblib.load(scaler_path)
    else:
        print('开始训练新XGBoost模型...')
        xgb_scaler = StandardScaler()
        X_scaled = xgb_scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=features, index=X.index)
        tscv = TimeSeriesSplit(n_splits=5)
        best_model = None
        for fold, (train_index, test_index) in enumerate(tscv.split(X)):
            print(f"Fold {fold+1}")
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            weight_train = sample_weight.iloc[train_index]
            weight_test = sample_weight.iloc[test_index]
            dtrain = xgb.DMatrix(X_train, label=y_train, weight=weight_train)
            dtest = xgb.DMatrix(X_test, label=y_test, weight=weight_test)
            pos_count = sum(y_train == 1)
            neg_count = sum(y_train == 0)
            scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0
            params = {
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'scale_pos_weight': scale_pos_weight,
                'learning_rate': 0.1,
                'max_depth': 6,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'seed': 42
            }
            xgb_model = xgb.train(
                params, dtrain, num_boost_round=1000,
                evals=[(dtrain, 'train'), (dtest, 'eval')],
                early_stopping_rounds=30,
                verbose_eval=50
            )
            score = xgb_model.get_score(importance_type='weight')
            print('特征重要性字典:', score)
            if not score:
                print('警告：模型未能分裂出有效特征，可能是样本太少或特征无效。')
            if fold == tscv.n_splits - 1:
                if score:
                    xgb.plot_importance(xgb_model, max_num_features=15)
                    plt.tight_layout()
                    plt.savefig('xgb_feature_importance.png')
                    plt.close()
                    print('XGBoost特征重要性已保存为 xgb_feature_importance.png')
                best_model = xgb_model
        best_model.save_model(model_path)
        joblib.dump(xgb_scaler, scaler_path)
        print(f'新XGBoost模型和scaler已保存')
        xgb_model = best_model
    return xgb_model, xgb_scaler

def train_lightgbm(X, y, features, sample_weight, model_path=None, scaler_path=None):
    if model_path is None:
        model_path = os.path.join(MODELS_DIR, 'lgb_model.txt')
    if scaler_path is None:
        scaler_path = os.path.join(MODELS_DIR, 'lgb_scaler.pkl')
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        print('已加载LightGBM模型和scaler')
        lgb_model = lgb.Booster(model_file=model_path)
        lgb_scaler = joblib.load(scaler_path)
    else:
        print('开始训练LightGBM新模型...')
        lgb_scaler = StandardScaler()
        X_scaled = lgb_scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=features, index=X.index)
        tscv = TimeSeriesSplit(n_splits=5)
        best_model = None
        for fold, (train_index, test_index) in enumerate(tscv.split(X)):
            print(f"LightGBM Fold {fold+1}")
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            weight_train = sample_weight.iloc[train_index]
            weight_test = sample_weight.iloc[test_index]
            lgb_train = lgb.Dataset(X_train, label=y_train, weight=weight_train, free_raw_data=False)
            lgb_eval = lgb.Dataset(X_test, label=y_test, weight=weight_test, free_raw_data=False)
            pos_count = sum(y_train == 1)
            neg_count = sum(y_train == 0)
            scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0
            params = {
                'objective': 'binary',
                'metric': 'auc',
                'reg_lambda': 1,
                'deterministic': True,
                'scale_pos_weight': 20,
                'feature_pre_filter': False
            }
            lgb_model = lgb.train(params, lgb_train, num_boost_round=1000, valid_sets=[lgb_train, lgb_eval])
            importances = lgb_model.feature_importance(importance_type='gain')
            feature_names = np.array(features)
            df_imp = pd.DataFrame({'feature': feature_names, 'importance': importances})
            df_imp = df_imp[df_imp['importance'] > 0].sort_values('importance', ascending=True)
            plt.figure(figsize=(10, 6))
            plt.barh(df_imp['feature'], df_imp['importance'])
            plt.xlabel('Importance')
            plt.ylabel('Feature name')
            plt.title(f'LightGBM Feature Importance Fold {fold+1}')
            plt.tight_layout()
            plt.savefig(f'lgb_feature_importance_fold{fold+1}.png')
            plt.close()
            print(f'LightGBM特征重要性已保存为 lgb_feature_importance_fold{fold+1}.png')
            if fold == tscv.n_splits - 1:
                best_model = lgb_model
        best_model.save_model(model_path)
        joblib.dump(lgb_scaler, scaler_path)
        print('LightGBM模型和scaler已保存')
    return lgb_model, lgb_scaler

# 融合预测函数
def fused_predict(xgb_model, lgb_model, scaler, data, features, xgb_weight=0.5, lgb_weight=0.5):
    features_scaled = scaler.transform(data[features])
    dmatrix = xgb.DMatrix(features_scaled, feature_names=features)
    xgb_proba = xgb_model.predict(dmatrix)
    lgb_proba = lgb_model.predict(features_scaled)
    return xgb_weight * xgb_proba + lgb_weight * lgb_proba

def predict_and_show_results(model, scaler, labeled_data, features):
    """使用模型进行预测并显示结果"""
    # 确定要预测的日期
    predict_date_str = datetime.datetime.now().strftime('%Y%m%d')
    date_info_str = f"今日({predict_date_str})"
    data_to_predict = labeled_data[(labeled_data['date'] == predict_date_str) & (labeled_data['ts_code'].str[2:5].isin(['300', '301']))]

    # 如果今日无数据，则使用最新的有数据的日期
    if data_to_predict.empty:
        predict_date_str = labeled_data['date'].max()
        date_info_str = f"最新数据({predict_date_str})"
        data_to_predict = labeled_data[(labeled_data['date'] == predict_date_str) & (labeled_data['ts_code'].str[2:5].isin(['300', '301']))]

    # 确保有数据可预测
    if not data_to_predict.empty:
        # 提取特征并使用加载/训练好的scaler进行缩放
        features_to_predict = data_to_predict[features]
        features_to_predict_scaled_np = scaler.transform(features_to_predict)
        # 将缩放后的numpy数组转回DataFrame，以保留特征名称
        features_to_predict_scaled = pd.DataFrame(features_to_predict_scaled_np, columns=features, index=features_to_predict.index)

        # 创建DMatrix并预测
        dcurrent = xgb.DMatrix(features_to_predict_scaled)
        probas = model.predict(dcurrent)
        
        # 整理并输出结果
        data_to_predict = data_to_predict.assign(probability=probas)
        data_to_predict['预测明日大涨10%概率(%)'] = (data_to_predict['probability'] * 100).round(2)
        selected = data_to_predict.nlargest(20, 'probability')
        
        print(f"\n使用{date_info_str}预测，创业板明日大涨10%概率最高的股票：")
        print(selected[['ts_code', 'name', 'date', 'close', 'probability', '预测明日大涨10%概率(%)']])
        
    else:
        print("无数据可用于预测。")

def evaluate_backtest(df, benchmark_col=None):
    # 超额收益
    if benchmark_col and benchmark_col in df.columns:
        df['excess_return'] = df['future_return'] - df[benchmark_col]
    else:
        df['excess_return'] = df['future_return']
    mean_excess = df['excess_return'].mean()
    std_excess = df['excess_return'].std()
    sharpe = mean_excess / std_excess if std_excess != 0 else np.nan
    sharpe_annual = sharpe * np.sqrt(252/5)
    # 胜率
    df['pred_up'] = df['prediction'] > 0
    df['real_up'] = df['future_return'] > 0
    win_count = ((df['pred_up']) & (df['real_up'])).sum()
    total_pred_up = df['pred_up'].sum()
    win_rate = win_count / total_pred_up if total_pred_up > 0 else np.nan
    # 盈亏比
    profit_trades = df[(df['pred_up']) & (df['future_return'] > 0)]['future_return']
    loss_trades = df[(df['pred_up']) & (df['future_return'] <= 0)]['future_return']
    avg_profit = profit_trades.mean() if not profit_trades.empty else 0
    avg_loss = loss_trades.mean() if not loss_trades.empty else 0
    pl_ratio = avg_profit / abs(avg_loss) if avg_loss != 0 else np.nan
    print(f'超额收益夏普比率（年化）: {sharpe_annual:.2f}')
    print(f'胜率: {win_rate:.2%}')
    print(f'盈亏比: {pl_ratio:.2f}')

def load_or_create(path, create_func, *args, **kwargs):
    """
    如果csv文件存在则加载，否则调用create_func生成并保存，然后返回DataFrame。
    create_func应返回DataFrame。
    """
    if os.path.exists(path):
        print(f'已加载 {os.path.basename(path)}')
        return pd.read_csv(path)
    else:
        print(f'正在生成 {os.path.basename(path)} ...')
        df = create_func(*args, **kwargs)
        df.to_csv(path, index=False, encoding='utf-8-sig')
        return df

def load_or_create_incremental(path, create_func, raw_data, *args, **kwargs):
    """
    增量式加载或创建技术指标数据。
    只对新增的原始数据行进行特征计算，并追加到已有文件。
    """
    if os.path.exists(path):
        print(f'已加载 {os.path.basename(path)}，将进行增量更新')
        tech_data = pd.read_csv(path)
        # 标识已处理过的 ts_code+date
        processed = set(zip(tech_data['ts_code'], tech_data['date']))
        # 找出未处理过的原始数据
        new_rows = raw_data[~raw_data.set_index(['ts_code', 'date']).index.isin(processed)]
        if not new_rows.empty:
            print(f'发现新增数据 {len(new_rows)} 条，正在增量计算...')
            new_tech = create_func(new_rows, *args, **kwargs)
            tech_data = pd.concat([tech_data, new_tech], ignore_index=True)
            tech_data.to_csv(path, index=False, encoding='utf-8-sig')
        else:
            print('没有新增数据，无需更新。')
        return tech_data
    else:
        print(f'未发现 {os.path.basename(path)}，将全量生成...')
        tech_data = create_func(raw_data, *args, **kwargs)
        tech_data.to_csv(path, index=False, encoding='utf-8-sig')
        return tech_data

def create_raw_data():
    print("获取本地通达信股票列表...")
    stock_list = get_stock_list()
    print(f"股票数: {len(stock_list)}")
    all_data = []
    for symbol in stock_list:
        data = get_local_data(symbol)
        if data is not None:
            all_data.append(data)
    if not all_data: return print("未获取到任何股票数据")
    stock_data = pd.concat(all_data, ignore_index=True)
    print("原始数据维度:", stock_data.shape)
    # 获取并合并股票名称
    name_map = get_stock_name_mapping()
    stock_data = pd.merge(stock_data, name_map, on='ts_code', how='left')
    # 只保留2024年9月1日及以后的数据
    stock_data = stock_data[stock_data['date'] >= '20240901']
    # 根据st_stocks.xlsx去除所有st、*st股票
    stock_data = filter_st_stocks(stock_data, st_file='st_stocks.xlsx')
    print("筛选后数据维度:", stock_data.shape)
    return stock_data

def main():
    model_path = os.path.join(MODELS_DIR, 'xgb_model.json')
    scaler_path = os.path.join(MODELS_DIR, 'xgb_scaler.pkl')
    lgb_model_path = os.path.join(MODELS_DIR, 'lgb_model.txt')
    lgb_scaler_path = os.path.join(MODELS_DIR, 'lgb_scaler.pkl')
    # --- 1. 数据加载与初步处理 ---
    stock_data = load_or_create('1_raw_data.csv', create_raw_data)
    # --- 2. 特征工程与标签创建（增量式）---
    tech_data = load_or_create_incremental('2_tech_data.csv', calculate_technical_features, stock_data, factor_switches=FACTOR_SWITCHES)
    # --- 3. 创建目标标签 ---
    print("创建目标标签...")
    labeled_data = create_target(tech_data)
    features_and_target = feature_selection(labeled_data) + ['target']
    print('特征列:', features_and_target)
    print('dropna前样本数:', labeled_data.shape)
    labeled_data = labeled_data.dropna(subset=['close', 'volume', 'target'])
    print('dropna后样本数:', labeled_data.shape)
    labeled_data.to_csv('3_labeled_data.csv', index=False, encoding='utf-8-sig')
    # --- 4. 模型训练与预测 ---
    train_data = labeled_data[labeled_data['ts_code'].str[2:5].isin(['300', '301'])].copy()
    train_data = train_data.sort_values('date')
    print(f"用于训练的创业板样本数: {len(train_data)}")
    features = feature_selection(train_data)
    X = train_data[features]
    y = train_data['target']
    sample_weight = train_data['sample_weight']
    # --- 严格时间序列验证集划分 ---
    # n = len(train_data)
    # split_idx = int(n * 0.8)
    # X_train = X.iloc[:split_idx]
    # X_val = X.iloc[split_idx:]
    # y_train = y.iloc[:split_idx]
    # y_val = y.iloc[split_idx:]
    # sw_train = sample_weight.iloc[:split_idx]
    # sw_val = sample_weight.iloc[split_idx:]
    # 直接用全部数据训练，交叉验证在模型内部完成
    X_train = X
    y_train = y
    sw_train = sample_weight
    # XGBoost
    xgb_model, xgb_scaler = train_xgb(X_train, y_train, features, sw_train, model_path=model_path, scaler_path=scaler_path)
    # LightGBM
    lgb_model, lgb_scaler = train_lightgbm(X_train, y_train, features, sw_train, model_path=lgb_model_path, scaler_path=lgb_scaler_path)
    # 计算AUC
    # dval = xgb.DMatrix(xgb_scaler.transform(X_val), feature_names=features)
    # xgb_val_proba = xgb_model.predict(dval)
    # lgb_val_proba = lgb_model.predict(lgb_scaler.transform(X_val))
    # xgb_val_auc = roc_auc_score(y_val, xgb_val_proba)
    # lgb_val_auc = roc_auc_score(y_val, lgb_val_proba)
    # print(f"XGBoost验证集AUC: {xgb_val_auc:.4f}")
    # print(f"LightGBM验证集AUC: {lgb_val_auc:.4f}")
    # if (xgb_val_auc + lgb_val_auc) > 0:
    #     xgb_weight = xgb_val_auc / (xgb_val_auc + lgb_val_auc)
    #     lgb_weight = 1 - xgb_weight
    # else:
    #     xgb_weight = 0.5
    #     lgb_weight = 0.5
    # print(f"融合权重: XGBoost={xgb_weight:.2f}, LightGBM={lgb_weight:.2f}")

    xgb_weight = 0.5
    lgb_weight = 0.5

    # --- 5. 结果展示（融合概率） ---
    predict_date_str = datetime.datetime.now().strftime('%Y%m%d')
    date_info_str = f"今日({predict_date_str})"
    data_to_predict = labeled_data[(labeled_data['date'] == predict_date_str) & (labeled_data['ts_code'].str[2:5].isin(['300', '301']))]
    if data_to_predict.empty:
        predict_date_str = labeled_data['date'].max()
        date_info_str = f"最新数据({predict_date_str})"
        data_to_predict = labeled_data[(labeled_data['date'] == predict_date_str) & (labeled_data['ts_code'].str[2:5].isin(['300', '301']))]
    if not data_to_predict.empty:
        features_to_predict = data_to_predict[features]
        features_scaled_xgb = xgb_scaler.transform(features_to_predict)
        features_scaled_lgb = lgb_scaler.transform(features_to_predict)
        dcurrent = xgb.DMatrix(features_scaled_xgb, feature_names=features)
        xgb_proba = xgb_model.predict(dcurrent)
        lgb_proba = lgb_model.predict(features_scaled_lgb)
        fused_proba = xgb_weight * xgb_proba + lgb_weight * lgb_proba
        data_to_predict = data_to_predict.assign(xgb_proba=xgb_proba, lgb_proba=lgb_proba, probability=fused_proba)
        data_to_predict['预测明日大涨10%概率(%)'] = (data_to_predict['probability'] * 100).round(2)
        selected = data_to_predict.nlargest(10, 'probability')
        selected_xgb = data_to_predict.nlargest(10, 'xgb_proba')
        selected_lgb = data_to_predict.nlargest(10, 'lgb_proba')
        # 打印时添加主力强度和情绪热度
        cols_base = ['ts_code', 'name', 'date', 'close']
        cols_extra = []
        if 'main_strength' in data_to_predict.columns:
            cols_extra.append('main_strength')
        if 'zt_ratio' in data_to_predict.columns:
            cols_extra.append('zt_ratio')
        print(f"\n使用{date_info_str}预测，创业板明日大涨10%概率最高的股票（XGBoost）：")
        print(selected_xgb[cols_base + ['xgb_proba'] + cols_extra])
        print(f"\n使用{date_info_str}预测，创业板明日大涨10%概率最高的股票（LightGBM）：")
        print(selected_lgb[cols_base + ['lgb_proba'] + cols_extra])
        print(f"\n使用{date_info_str}预测，创业板明日大涨10%概率最高的股票（融合XGBoost+LightGBM）：")
        print(selected[cols_base + ['probability', '预测明日大涨10%概率(%)'] + cols_extra])
    else:
        print("无数据可用于预测。")

if __name__ == "__main__":
    main()