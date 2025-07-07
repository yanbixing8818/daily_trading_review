import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from mootdx.reader import Reader
from mootdx.quotes import Quotes
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import talib
import os
import logging
from datetime import datetime, timedelta
import joblib
import glob
import matplotlib.pyplot as plt
import matplotlib
import baostock as bs
from mootdx.affair import Affair
import csv

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 配置日志和参数
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {
    'tdx_path': '/mnt/c/new_tdx',      # 通达信数据目录
    'model_dir': 'models',         # 模型保存目录
    'data_days': 60,               # 历史数据天数
    'test_size': 0.2,              # 测试集比例
    'top_n': 10,                   # 每日选股数量
    'fusion_weights': (0.4, 0.6)  # XGBoost和LightGBM融合权重
}

# 特征英文名到中文名的映射
FEATURE_NAME_MAP = {
    'ret_1d': '1日收益率',
    'volatility_5d': '5日波动率',
    'MA_5': '5日均线',
    'MA_10': '10日均线',
    'MA_20': '20日均线',
    'MACD': 'MACD',
    'MACD_Signal': 'MACD信号线',
    'RSI_14': '14日RSI',
    'pre_open_change': '竞价涨跌幅',
    'pre_volume_ratio': '竞价量比',
    'open': '开盘价',
    'close': '收盘价',
    'high': '最高价',
    'low': '最低价',
    'volume': '成交量',
    'pre_open': '竞价开盘价',
    'pre_volume': '竞价成交量',
    'turnover_rate': '换手率',
    'volume_ratio': '量比',
    'dde_net_large_order_volume': 'DDE大单净量',
    'chip_bottom_ratio_20d': '20日底部筹码比例',
    'chip_top_ratio_20d': '20日顶部筹码比例',
    'chip_stability_20d': '20日筹码稳定性',
}

# ========== 获取本地A股代码列表 ==========
def get_stock_list():
    """
    从本地通达信目录提取A股代码（不联网）。
    只保留以下板块：
    - 沪市主板：600、601、603、605开头（上交所）
    - 科创板：688开头（上交所）
    - 深市主板：000、001、002、003开头（深交所）
    - 创业板：300、301开头（深交所）
    - 北交所普通股：83、87开头（北交所）
    返回格式如sh600000、sz000001。
    """
    tdx_path = CONFIG['tdx_path']
    code_set = set()
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(tdx_path, f'vipdoc/{market}/lday')
        print(f"检查目录: {lday_dir}, 存在: {os.path.exists(lday_dir)}")
        if not os.path.exists(lday_dir):
            continue
        files = glob.glob(os.path.join(lday_dir, '*.day'))
        print(f"{market}市场day文件数: {len(files)}")
        for f in files:
            fname = os.path.splitext(os.path.basename(f))[0]
            # 只要以sh/sz开头，后面全为数字
            if (fname.startswith('sh') or fname.startswith('sz')) and fname[2:].isdigit():
                code = fname[2:]
                # 只保留指定板块规则
                if (
                    # code.startswith(('600', '601', '603', '605')) or
                    # code.startswith('688') or
                    # code.startswith(('000', '001', '002', '003')) or
                    # code.startswith(('300', '301')) or
                    # code.startswith(('83', '87'))
                    code.startswith(('300', '301'))
                ):
                    code_set.add(fname)
    code_list = sorted(code_set)
    logger.info(f"本地A股代码数: {len(code_list)}")
    return code_list

# ========== 直接粘贴 get_outstanding_map_from_tdx 实现 ==========
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
    # 下载所有财务文件到tmp目录
    affair_reader.fetch(downdir=tmp_dir)
    # 自动查找最新zip
    if zip_filename is None:
        files = [f for f in os.listdir(tmp_dir) if f.startswith('gpcw') and f.endswith('.zip')]
        if not files:
            raise FileNotFoundError('未找到gpcw*.zip财务文件')
        zip_filename = sorted(files)[-1]
    print("选用zip文件：", zip_filename)
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

# ========== mootdx本地流通股本批量抓取（Affair方式） ==========
def get_outstanding_map_tdx(csv_path='outstanding_map.csv', tdx_path=CONFIG['tdx_path']):
    """
    优先用本地通达信财务数据批量提取流通股本，保存为csv，后续直接读取。
    :param csv_path: 本地缓存文件路径
    :param tdx_path: 通达信目录
    :return: symbol->outstanding字典（单位：股）
    """
    if os.path.exists(csv_path):
        df_out = pd.read_csv(csv_path, dtype={'code': str})
        # 兼容老字段名
        if 'symbol' in df_out.columns and 'outstanding' in df_out.columns:
            return dict(zip(df_out['symbol'], df_out['outstanding']))
        elif 'code' in df_out.columns and 'outstanding' in df_out.columns:
            return dict(zip(df_out['code'], df_out['outstanding']))
        else:
            print(f"警告：{csv_path} 文件格式异常，将重新生成。")
            os.remove(csv_path)
    # 用新函数生成
    return get_outstanding_map_from_tdx(tdx_path=tdx_path, csv_path=csv_path)


# ========== 在calculate_features中集成真实流通股本 ==========
# 全局加载一次outstanding_map（优先用本地通达信）
OUTSTANDING_MAP = get_outstanding_map_from_tdx(
    tdx_path=CONFIG['tdx_path'],
    csv_path='outstanding_map.csv',
    zip_filename='gpcw20250331.zip'
)

def get_local_data(symbol, days=CONFIG['data_days']):
    """
    获取本地日线数据，保证date列为字符串格式
    """
    try:
        reader = Reader.factory(market='std', tdxdir=CONFIG['tdx_path'])
        daily_data = reader.daily(symbol=symbol)
        if daily_data is None or len(daily_data) < days:
            return None
        # 补齐date字段
        if 'date' not in daily_data.columns:
            # mootdx 0.9.7+ 会自动有date字段，老版本没有
            # 尝试用index补齐
            if hasattr(daily_data.index, 'to_timestamp') or isinstance(daily_data.index, pd.DatetimeIndex):
                daily_data = daily_data.copy()
                daily_data['date'] = daily_data.index.strftime('%Y%m%d')
            else:
                # 兜底：用range生成假日期（不推荐，建议升级mootdx）
                daily_data = daily_data.copy()
                daily_data['date'] = pd.Series(
                    pd.date_range(end=pd.Timestamp.today(), periods=len(daily_data))
                ).dt.strftime('%Y%m%d').values
        else:
            daily_data['date'] = daily_data['date'].dt.strftime('%Y%m%d')
        print(f"{symbol} 数据行数: {len(daily_data)}, 列: {list(daily_data.columns)}")
        return daily_data.tail(days)
    except Exception as e:
        logger.error(f"获取{symbol}数据失败: {str(e)}")
        return None

def get_auction_features(symbol, date, tdx_path=CONFIG['tdx_path']):
    reader = Reader.factory(market='std', tdxdir=tdx_path)
    try:
        df_min = reader.minute(symbol=symbol)
    except Exception:
        df_min = None
    auction_features = {}
    if df_min is not None and not df_min.empty:
        # 适配 index 为 DatetimeIndex 的情况
        if isinstance(df_min.index, pd.DatetimeIndex):
            df_min = df_min.copy()
            df_min['date_str'] = df_min.index.strftime('%Y%m%d')
            df_min['time_str'] = df_min.index.strftime('%H%M')
            df_min = df_min[df_min['date_str'] == str(date)]
            # df_auction = df_min[df_min['time_str'].between('0915', '0930')]   //为竞价留的接口
            df_auction = df_min[df_min['time_str'] == '0931']
            auction_features['auction_volume'] = df_auction['volume'].sum()
            auction_features['auction_amount'] = df_auction['amount'].sum()
            auction_features['auction_avg_price'] = (df_auction['amount'].sum() / df_auction['volume'].sum()
                                                     if df_auction['volume'].sum() > 0 else np.nan)
        else:
            # 其它结构，保持原逻辑
            auction_features['auction_volume'] = np.nan
            auction_features['auction_amount'] = np.nan
            auction_features['auction_avg_price'] = np.nan
    else:
        auction_features['auction_volume'] = np.nan
        auction_features['auction_amount'] = np.nan
        auction_features['auction_avg_price'] = np.nan
    # 分笔特征本地没有，直接填NaN
    auction_features['tick_auction_volume'] = np.nan
    auction_features['tick_auction_amount'] = np.nan
    auction_features['tick_auction_avg_price'] = np.nan
    return auction_features

def calculate_features(df, symbol=None):
    try:
        if 'date' not in df.columns:
            raise ValueError("输入数据缺少 date 字段")
        df = df.copy()
        df['date'] = df['date'].astype(str)
        result = pd.DataFrame()
        result['date'] = df['date']
        # result['ret_1d'] = df['close'].pct_change()  # 移除1日收益率因子
        result['volatility_5d'] = df['close'].pct_change().rolling(5).std()
        result['MA_5'] = talib.MA(df['close'], timeperiod=5)
        result['MA_10'] = talib.MA(df['close'], timeperiod=10)
        result['MA_20'] = talib.MA(df['close'], timeperiod=20)
        macd, macdsignal, _ = talib.MACD(df['close'])
        result['MACD'] = macd
        result['MACD_Signal'] = macdsignal
        result['RSI_14'] = talib.RSI(df['close'], timeperiod=14)
        # 目标变量
        result['target'] = (df['close'] / df['close'].shift(1) >= 1.10).astype(int)
        # 自动合并分时/分笔特征
        if symbol is not None:
            auction_feature_dicts = []
            for date in result['date']:
                feats = get_auction_features(symbol, date)
                auction_feature_dicts.append(feats)
            auction_df = pd.DataFrame(auction_feature_dicts)
            auction_df.index = result.index
            result = pd.concat([result, auction_df], axis=1)
        # 换手率 = 当日成交量 / 流通股本（如有outstanding字段）
        if 'outstanding' not in df.columns and symbol is not None:
            code6 = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            df['outstanding'] = OUTSTANDING_MAP.get(code6, np.nan)
        if 'outstanding' in df.columns:
            result['turnover_rate'] = df['volume'] / df['outstanding']
        else:
            result['turnover_rate'] = None  # 或np.nan
        # 量比 = 当日成交量 / (前5日平均成交量/240)
        if len(df) > 5:
            avg_5d_vol = df['volume'].iloc[-6:-1].mean()
            result['volume_ratio'] = df['volume'] / (avg_5d_vol / 240)
        else:
            result['volume_ratio'] = None  # 或np.nan
        # DDE大单净量 = （大单买入量 - 大单卖出量）/ 流通股本 × 100%
        # 用1分钟线近似tick，使用mootdx的minute方法
        result['dde_net_large_order_volume'] = None  # 默认无分钟线
        try:
            if symbol is not None:
                minute_reader = Reader.factory(market='std', tdxdir=CONFIG['tdx_path'])
                min1_df = minute_reader.minute(symbol=symbol)
                if min1_df is not None and not min1_df.empty:
                    logging.debug(f"{symbol} 分钟线字段: {min1_df.columns}")
                    logging.debug(f"{symbol} 分钟线 index: {min1_df.index}")
                    logging.debug(f"{symbol} 分钟线 index type: {type(min1_df.index)}")
                    last_date = df['date'].iloc[-1]
                    # 兼容index为DatetimeIndex、date、datetime字段
                    if isinstance(min1_df.index, pd.DatetimeIndex):
                        min1_df['date'] = min1_df.index.strftime('%Y%m%d').astype(int)
                        min1_df = min1_df[min1_df['date'] == int(last_date)]
                    elif 'date' in min1_df.columns:
                        if min1_df['date'].dtype != int:
                            min1_df['date'] = min1_df['date'].astype(int)
                        min1_df = min1_df[min1_df['date'] == int(last_date)]
                    elif 'datetime' in min1_df.columns:
                        min1_df['date'] = min1_df['datetime'].astype(str).str[:8].astype(int)
                        min1_df = min1_df[min1_df['date'] == int(last_date)]
                    else:
                        logging.debug(f"{symbol} 分钟线数据无date或datetime字段，无法筛选当日")
                        min1_df = None
                    if min1_df is not None and not min1_df.empty:
                        # 近似tick：大单=单分钟成交量>=100000
                        large_orders = min1_df[min1_df['volume'] >= 100000]
                        buy_vol = large_orders[large_orders['close'] > large_orders['open']]['volume'].sum()
                        sell_vol = large_orders[large_orders['close'] < large_orders['open']]['volume'].sum()
                        logging.debug(f"{symbol} {last_date} 大单买入量: {buy_vol}, 大单卖出量: {sell_vol}, 大单总数: {len(large_orders)}")
                        if 'outstanding' in df.columns and df['outstanding'].iloc[-1] > 0:
                            result['dde_net_large_order_volume'] = (buy_vol - sell_vol) / df['outstanding'].iloc[-1] * 100
                        else:
                            logging.debug(f"{symbol} 缺少流通股本字段，无法计算DDE大单净量")
                    else:
                        logging.debug(f"{symbol} 无法读取分钟线数据或数据为空")
        except Exception as e:
            logging.warning(f"{symbol} 计算DDE大单净量异常: {e}")
        # 筹码集中度因子
        result['chip_bottom_ratio_20d'] = df['close'].rolling(20).apply(
            lambda x: get_chip_ratio(pd.DataFrame({'close': x}), price_range=(0, 0.3), days=20), raw=False)
        result['chip_top_ratio_20d'] = df['close'].rolling(20).apply(
            lambda x: get_chip_ratio(pd.DataFrame({'close': x}), price_range=(0.7, 1), days=20), raw=False)
        result['chip_stability_20d'] = df['close'].rolling(20).apply(
            lambda x: chip_stability(pd.DataFrame({'close': x}), days=20), raw=False)
        # 输出调试日志
        try:
            last_idx = result.index[-1]
            feature_log = {col: result.loc[last_idx, col] for col in result.columns if col != 'date'}
            logging.info(f"{symbol} 所有特征最后一行: {feature_log}")
        except Exception as e:
            logging.warning(f"{symbol} 特征日志输出异常: {e}")
        # 注意：如有特征变动，需删除旧模型文件并重新训练模型，保证特征数一致。
        return result.dropna(subset=['target'])
    except Exception as e:
        logger.error(f"特征计算失败: {str(e)}")
        return None

def prepare_dataset(stock_list):
    X, y = [], []
    all_feature_names = set()
    features_list = []
    for symbol in stock_list:
        data = get_local_data(symbol)
        if data is None:
            print(f"{symbol} 无本地数据")
            continue
        data_with_features = calculate_features(data, symbol=symbol)
        if data_with_features is None or data_with_features.empty:
            print(f"{symbol} 特征为空")
            continue
        features = data_with_features.drop(['target'], axis=1)
        all_feature_names.update(features.columns)
        features_list.append((features, data_with_features['target']))
    all_feature_names = sorted(all_feature_names)
    for features, targets in features_list:
        features = features.reindex(columns=all_feature_names, fill_value=np.nan)
        X.extend(features.values)
        y.extend(targets.values)
    print(f"最终特征样本数: {len(X)}")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    return X_scaled, np.array(y), scaler, all_feature_names

def train_xgboost(X_train, y_train, X_val, y_val):
    """
    训练XGBoost模型[6,8](@ref)
    """
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'max_depth': 5,
        'learning_rate': 0.05,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'gamma': 0.1,
        'min_child_weight': 3,
        'n_estimators': 1000
    }
    
    model = xgb.XGBClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=50,
        verbose=10
    )
    return model

def train_lightgbm(X_train, y_train, X_val, y_val):
    """
    训练LightGBM模型[9,12](@ref)
    """
    params = {
        'boosting_type': 'gbdt',
        'objective': 'binary',
        'metric': 'binary_logloss',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1
    }
    
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
    
    model = lgb.train(
        params,
        train_data,
        num_boost_round=1000,
        valid_sets=[val_data],
        callbacks=[lgb.early_stopping(stopping_rounds=50)]
    )
    return model

def save_models(models, scaler):
    """保存模型和标准化器"""
    os.makedirs(CONFIG['model_dir'], exist_ok=True)
    models[0].save_model(os.path.join(CONFIG['model_dir'], 'xgboost_model.json'))
    joblib.dump(models[1], os.path.join(CONFIG['model_dir'], 'lightgbm_model.txt'))
    joblib.dump(scaler, os.path.join(CONFIG['model_dir'], 'scaler.pkl'))
    logger.info("模型保存完成")

def load_models():
    """加载预训练模型"""
    xgb_model = xgb.XGBClassifier()
    xgb_model.load_model(os.path.join(CONFIG['model_dir'], 'xgboost_model.json'))
    
    lgb_model = joblib.load(os.path.join(CONFIG['model_dir'], 'lightgbm_model.txt'))
    scaler = joblib.load(os.path.join(CONFIG['model_dir'], 'scaler.pkl'))
    return xgb_model, lgb_model, scaler

def daily_selection(models, scaler):
    today = datetime.now().strftime("%Y-%m-%d")
    selected_stocks = []
    stock_list = get_stock_list()
    for symbol in stock_list:
        data = get_local_data(symbol)
        if data is None or len(data) < 5:
            continue
        latest_data = calculate_features(data, symbol=symbol).iloc[-1:].drop(['target'], axis=1)
        if latest_data.empty:
            continue
        X_scaled = scaler.transform(latest_data.values)
        xgb_proba = models[0].predict_proba(X_scaled)[0][1]
        lgb_proba = models[1].predict(X_scaled)[0]
        fused_proba = (CONFIG['fusion_weights'][0] * xgb_proba + CONFIG['fusion_weights'][1] * lgb_proba)
        selected_stocks.append({
            'symbol': symbol,
            'probability': fused_proba,
            'pre_open': data.iloc[-1]['open'],
            'last_close': data.iloc[-2]['close'],
            'pre_change': (data.iloc[-1]['open'] / data.iloc[-2]['close'] - 1) * 100
        })
    selected_stocks.sort(key=lambda x: x['probability'], reverse=True)
    return selected_stocks[:CONFIG['top_n']]

def save_results(results, filename="selected_stocks.csv"):
    """保存选股结果"""
    if not results:
        logger.warning("未选出符合条件的股票")
        return
    
    df = pd.DataFrame(results)
    df['date'] = datetime.now().strftime("%Y-%m-%d")
    df['pre_change'] = (df['pre_open'] / df['last_close'] - 1) * 100
    
    # 保存到CSV
    if os.path.exists(filename):
        df.to_csv(filename, mode='a', header=False, index=False)
    else:
        df.to_csv(filename, index=False)
    logger.info(f"选股结果已保存到{filename}")

def plot_and_save_feature_importance(model, feature_names, model_type, filename):
    """
    绘制并保存特征重要性条形图
    model_type: 'xgb' 或 'lgb'
    """
    if model_type == 'xgb':
        importances = model.feature_importances_
    elif model_type == 'lgb':
        importances = model.feature_importance(importance_type='gain')
    else:
        raise ValueError('未知模型类型')
    indices = np.argsort(importances)[::-1]
    plt.figure(figsize=(10, 6))
    plt.title(f"{model_type.upper()} Feature Importance")
    plt.bar(range(len(importances)), importances[indices], align="center")
    # 用中文名，没有映射的用原名
    chinese_names = [FEATURE_NAME_MAP.get(name, name) for name in np.array(feature_names)[indices]]
    plt.xticks(range(len(importances)), chinese_names, rotation=90)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    logger.info(f"{model_type.upper()}特征重要性已保存到 {filename}")

def backtest_selection(models, scaler, date_str):
    selected_stocks = []
    stock_list = get_stock_list()
    for symbol in stock_list:
        data = get_local_data(symbol)
        if data is None or len(data) < 5:
            continue
        features_df = calculate_features(data, symbol=symbol)
        if features_df is None or features_df.empty or 'date' not in features_df.columns:
            print(f"{symbol} 特征无date列，跳过")
            continue
        row = features_df[features_df['date'] == date_str]
        if row.empty:
            continue
        latest_data = row.drop(['target', 'date'], axis=1)
        X_scaled = scaler.transform(latest_data.values)
        xgb_proba = models[0].predict_proba(X_scaled)[0][1]
        lgb_proba = models[1].predict(X_scaled)[0]
        fused_proba = (CONFIG['fusion_weights'][0] * xgb_proba + CONFIG['fusion_weights'][1] * lgb_proba)
        prev_close = None
        if not data.loc[data['date'] < date_str].empty:
            prev_close = data.loc[data['date'] < date_str, 'close'].iloc[-1]
        pre_open = row.iloc[0].get('pre_open', None)
        selected_stocks.append({
            'symbol': symbol,
            'probability': fused_proba,
            'pre_open': pre_open,
            'last_close': prev_close,
            'pre_change': ((pre_open or 0) / (prev_close if prev_close else 1) - 1) * 100 if pre_open is not None and prev_close else None
        })
    selected_stocks.sort(key=lambda x: x['probability'], reverse=True)
    return selected_stocks[:CONFIG['top_n']]

def get_chip_ratio(df, price_range=(0, 0.3), days=20):
    if len(df) < days:
        return np.nan
    closes = df['close'].tail(days)
    min_p = closes.min()
    max_p = closes.max()
    if max_p == min_p:
        return 1.0
    normed = (closes - min_p) / (max_p - min_p)
    ratio = ((normed >= price_range[0]) & (normed <= price_range[1])).sum() / days
    return ratio

def chip_stability(df, days=20):
    bottom_ratio = get_chip_ratio(df, price_range=(0, 0.3), days=days)
    current_ratio = get_chip_ratio(df, price_range=(0.7, 1), days=days)
    return int(bottom_ratio > 0.65 and current_ratio < 0.21)

def main():
    """
    主程序流程：
    - 训练或加载模型
    - 每日选股
    - 输出和保存结果
    - 新增：保存整理好的训练特征数据到csv
    """
    os.makedirs(CONFIG['model_dir'], exist_ok=True)
    
    # 模型训练或加载
    if all(os.path.exists(os.path.join(CONFIG['model_dir'], f)) 
           for f in ['xgboost_model.json', 'lightgbm_model.txt', 'scaler.pkl']):
        logger.info("加载预训练模型")
        xgb_model, lgb_model, scaler = load_models()
        models = (xgb_model, lgb_model)
        feature_df = pd.read_csv('train_features.csv')
        feature_names = feature_df.columns[:-1]  # 最后一列是label
    else:
        logger.info("训练新模型")
        stock_list = get_stock_list()
        print("调试用股票列表：", stock_list)
        X, y, scaler, feature_columns = prepare_dataset(stock_list)
        feature_df = pd.DataFrame(X, columns=feature_columns)
        feature_df['label'] = y
        feature_df.to_csv('train_features.csv', index=False)
        logger.info("已保存训练特征数据到 train_features.csv")
        feature_names = feature_df.columns[:-1]
        # 数据集划分
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=CONFIG['test_size'], random_state=42
        )
        # 训练模型
        logger.info("训练XGBoost模型...")
        xgb_model = train_xgboost(X_train, y_train, X_test, y_test)
        logger.info("训练LightGBM模型...")
        lgb_model = train_lightgbm(X_train, y_train, X_test, y_test)
        models = (xgb_model, lgb_model)
        save_models(models, scaler)
    # 特征重要性分析并保存图片
    plot_and_save_feature_importance(models[0], feature_names, 'xgb', 'xgb_feature_importance.png')
    plot_and_save_feature_importance(models[1], feature_names, 'lgb', 'lgb_feature_importance.png')
    
    # 每日选股
    logger.info("开始每日选股...")
    selected_stocks = daily_selection(models, scaler)
    
    # 输出结果
    if selected_stocks:
        logger.info("今日推荐股票:")
        for i, stock in enumerate(selected_stocks, 1):
            logger.info(f"{i}. {stock['symbol']} - 概率: {stock['probability']:.2%} - 竞价涨幅: {stock['pre_change']:.2f}%")
    else:
        logger.info("今日无符合条件股票")
    
    # 保存结果
    save_results(selected_stocks)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # 回测模式
        date_str = sys.argv[1]
        logger.info(f"历史回测，指定日期：{date_str}")
        xgb_model, lgb_model, scaler = load_models()
        models = (xgb_model, lgb_model)
        selected_stocks = backtest_selection(models, scaler, date_str)
        save_results(selected_stocks, filename=f"backtest_selected_{date_str}.csv")
    else:
        main()