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

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
from sklearn.model_selection import TimeSeriesSplit

# 通达信数据目录（请根据实际情况修改）
TDX_PATH = '/mnt/c/new_tdx'

def get_stock_name_mapping():
    """使用baostock获取A股代码和名称的映射，带本地缓存"""
    cache_file = 'stock_name_mapping.csv'
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

def get_outstanding_map_from_tdx(tdx_path, csv_path='outstanding_map.csv', zip_filename=None):
    """
    从本地通达信财务数据（gpcw*.zip）提取所有A股流通股本，保存为csv，并返回dict。
    :param tdx_path: 通达信目录
    :param csv_path: 输出csv路径
    :param zip_filename: 财务zip文件名（如gpcw20241231.zip），默认自动查找最新
    :return: {code: outstanding}
    """
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
    csv_path='outstanding_map.csv',
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
    st_path = os.path.join(os.getcwd(), st_file)
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
    'dde_net_large_order_volume': True,
    'pct_chg': True,
    'amplitude': True,
    # 如需添加更多因子，继续补充
}

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
        
        # 量比 = 当日成交量 / (前5日平均成交量/240)   ！！！！！！！！这里需要考虑涨停板对于量能的影响情况！！！！！！！
        if 'volume' in group.columns and len(group) > 5:
            avg_5d_vol = pd.Series(group['volume']).rolling(5).mean()
            df.loc[idx, 'volume_ratio'] = group['volume'] / (avg_5d_vol / 240)
        else:
            df.loc[idx, 'volume_ratio'] = np.nan
        
        # DDE大单净量
        if factor_switches.get('dde_net_large_order_volume', False):
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
                else:
                    df.loc[idx, 'dde_net_large_order_volume'] = np.nan
            except Exception as e:
                df.loc[idx, 'dde_net_large_order_volume'] = np.nan
        else:
            df.loc[idx, 'dde_net_large_order_volume'] = np.nan

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
        df.loc[idx, 'MACD_Signal'] = macdsignal
        
        # RSI
        df.loc[idx, 'rsi'] = talib.RSI(close, timeperiod=14)
        df.loc[idx, 'RSI_14'] = talib.RSI(close, timeperiod=14)
        
        # 布林带
        upper, middle, lower = talib.BBANDS(close, timeperiod=20)
        df.loc[idx, 'boll_upper'] = upper
        df.loc[idx, 'boll_mid'] = middle
        df.loc[idx, 'boll_lower'] = lower
        
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
        if factor_switches.get('pct_chg', True):
            df.loc[idx, 'pct_chg_3d'] = pd.Series(close).pct_change(3).values
            df.loc[idx, 'pct_chg_5d'] = pd.Series(close).pct_change(5).values
            df.loc[idx, 'pct_chg_10d'] = pd.Series(close).pct_change(10).values
        else:
            df.loc[idx, 'pct_chg_3d'] = np.nan
            df.loc[idx, 'pct_chg_5d'] = np.nan
            df.loc[idx, 'pct_chg_10d'] = np.nan
            
        # 新增：3日、5日、10日震荡因子（振幅）
        if factor_switches.get('amplitude', True):
            df.loc[idx, 'amplitude_3d'] = (group['high'].rolling(3).max() - group['low'].rolling(3).min()) / group['low'].rolling(3).min()
            df.loc[idx, 'amplitude_5d'] = (group['high'].rolling(5).max() - group['low'].rolling(5).min()) / group['low'].rolling(5).min()
            df.loc[idx, 'amplitude_10d'] = (group['high'].rolling(10).max() - group['low'].rolling(10).min()) / group['low'].rolling(10).min()
        else:
            df.loc[idx, 'amplitude_3d'] = np.nan
            df.loc[idx, 'amplitude_5d'] = np.nan
            df.loc[idx, 'amplitude_10d'] = np.nan

    # 2. 形态信号特征 (在所有基础指标计算后进行)
    # 新高
    df['is_new_high'] = (df['close'] == df.groupby('ts_code')['close'].transform(lambda x: x.rolling(high_window, min_periods=1).max())).astype(int)
    # 均线多头排列
    df['multi_ma'] = ((df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20']) & (df['ma20'] > df['ma60'])).astype(int)
    # 放量突破60日线
    df['ma60_cross'] = ((df['close'] > df['ma60']) & (df.groupby('ts_code')['close'].shift(1) <= df.groupby('ts_code')['ma60'].shift(1))).astype(int)
    df['vol_ma20'] = df.groupby('ts_code')['volume'].transform(lambda x: x.rolling(vol_window).mean())
    df['vol_break'] = (df['volume'] > df['vol_ma20'] * vol_ratio).astype(int)
    
    return df

def create_target(df, next_day_thresh=0.1, neg_weight=10.0):
    """只创建目标标签和样本权重"""
    df = df.copy()
    df['next_day_return'] = df.groupby('ts_code')['close'].transform(lambda x: x.shift(-1) / x - 1)
    df['target'] = (df['next_day_return'] >= next_day_thresh).astype(int)
    # 增加负样本权重：对跌幅>7%的样本赋予更高权重
    df['sample_weight'] = 1.0
    df.loc[df['next_day_return'] <= -0.07, 'sample_weight'] = neg_weight
    return df

def feature_selection(df):
    features = [
        'open', 'high', 'low', 'close', 'volume', 'amount',
        '市值', '市值_log', '量价比',
        'ma5', 'ma10', 'ma20', 'ma60', 'macd', 'signal', 'MACD_Signal', 'rsi', 'RSI_14',
        'boll_mid', 'boll_upper', 'boll_lower',
        'chip_bottom_ratio_20d', 'chip_top_ratio_20d', 'chip_stability_20d',
        'pct_chg_3d', 'pct_chg_5d', 'pct_chg_10d',
        'amplitude_3d', 'amplitude_5d', 'amplitude_10d',  # 新增震荡因子
        'close_lag1', 'close_lag2', 'close_lag3',
        'volume_lag1', 'volume_lag2', 'volume_lag3',
        # 新增的形态特征
        'is_new_high', 'multi_ma', 'ma60_cross', 'vol_break',
        # 新增换手率
        'turnover_rate',
        # 新增DDE大单净量
        'dde_net_large_order_volume'
    ]
    features = [f for f in features if f in df.columns]
    return features

def train_or_load_model(X, y, features, sample_weight, model_path='xgb_model.json', scaler_path='scaler.pkl'):
    """加载或训练XGBoost模型"""
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        print('已加载模型和scaler')
        model = xgb.Booster()
        model.load_model(model_path)
        scaler = joblib.load(scaler_path)
    else:
        print('开始训练新模型...')
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=features, index=X.index)
        
        tscv = TimeSeriesSplit(n_splits=5)
        best_model = None
        
        for fold, (train_index, test_index) in enumerate(tscv.split(X)):
            print(f"Fold {fold+1}")
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            
            # 获取对应权重
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
            
            model = xgb.train(
                params, dtrain, num_boost_round=1000,
                evals=[(dtrain, 'train'), (dtest, 'eval')],
                early_stopping_rounds=30,
                verbose_eval=50
            )
            
            score = model.get_score(importance_type='weight')
            print('特征重要性字典:', score)
            if not score:
                print('警告：模型未能分裂出有效特征，可能是样本太少或特征无效。')
            
            if fold == tscv.n_splits - 1:
                if score:
                    xgb.plot_importance(model, max_num_features=15)
                    plt.tight_layout()
                    plt.savefig('feature_importance.png')
                    plt.close()
                    print('特征重要性已保存为 feature_importance.png')
                best_model = model
        
        best_model.save_model(model_path)
        joblib.dump(scaler, scaler_path)
        print(f'新模型和scaler已保存')
        model = best_model
        
    return model, scaler

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
    stock_data = filter_st_stocks(stock_data)
    print("筛选后数据维度:", stock_data.shape)
    return stock_data

def main():
    model_path = 'xgb_model.json'
    scaler_path = 'scaler.pkl'
    
    # --- 1. 数据加载与初步处理 ---
    stock_data = load_or_create('1_raw_data.csv', create_raw_data)
    
    # --- 2. 特征工程与标签创建（增量式）---
    tech_data = load_or_create_incremental('3_tech_data.csv', calculate_technical_features, stock_data, factor_switches=FACTOR_SWITCHES)
    
    # --- 3. 创建目标标签 ---
    print("创建目标标签...")
    labeled_data = create_target(tech_data)
    
    # 使用更精确的dropna，只对特征列和目标列进行检查
    features_and_target = feature_selection(labeled_data) + ['target']
    print('特征列:', features_and_target)
    print('dropna前样本数:', labeled_data.shape)
    labeled_data = labeled_data.dropna(subset=['close', 'volume', 'target'])  # 只对核心特征和target做dropna
    print('dropna后样本数:', labeled_data.shape)
    labeled_data.to_csv('4_labeled_data.csv', index=False, encoding='utf-8-sig')
    
    # --- 4. 模型训练与预测 ---
    # 使用所有创业板股票进行训练，不再进行额外的样本筛选
    # 创业板股票筛选（ts_code以'300'或'301'开头）
    train_data = labeled_data[labeled_data['ts_code'].str[2:5].isin(['300', '301'])].copy()
    
    print(f"用于训练的创业板样本数: {len(train_data)}")
    features = feature_selection(train_data)
    X = train_data[features]
    y = train_data['target']
    sample_weight = train_data['sample_weight']
    
    model, scaler = train_or_load_model(X, y, features, sample_weight, model_path=model_path, scaler_path=scaler_path)
    
    # --- 5. 结果展示 ---
    predict_and_show_results(model, scaler, labeled_data, features)

if __name__ == "__main__":
    main()