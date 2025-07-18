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
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 通达信数据目录（请根据实际情况修改）
TDX_PATH = '/mnt/c/new_tdx'

# 获取本地A股代码列表（参考double_model.py）
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

# 获取本地日线数据（参考double_model.py）
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

def preprocess_data(df):
    df = df.replace(['--', 'NaN', 'NA'], np.nan)
    df = df.dropna()
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # 衍生特征
    if 'close' in df.columns and 'volume' in df.columns:
        df['市值'] = df['close'] * df['volume']
        df['市值_log'] = np.log(df['市值'] + 1)
        df['量价比'] = df['volume'] / (df['close'].abs() + 0.01)
    return df

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

def calculate_technical_features(df):
    # 计算技术指标，按每只股票分组
    df = df.copy()
    for code, group in df.groupby('ts_code'):
        idx = group.index
        close = group['close'].values
        volume = group['volume'].values if 'volume' in group.columns else None
        # 均线
        df.loc[idx, 'ma5'] = talib.MA(close, timeperiod=5)
        df.loc[idx, 'ma10'] = talib.MA(close, timeperiod=10)
        df.loc[idx, 'ma20'] = talib.MA(close, timeperiod=20)
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
        # 动量特征
        df.loc[idx, 'momentum'] = pd.Series(close).pct_change(5).values
    return df

def prepare_labels(df):
    df['future_return'] = df.groupby('ts_code')['close'].transform(lambda x: x.shift(-5) / x - 1)
    df['label'] = df['future_return']
    return df

def feature_selection(df):
    features = [
        'open', 'high', 'low', 'close', 'volume', 'amount',
        '市值', '市值_log', '量价比',
        'ma5', 'ma10', 'ma20', 'macd', 'signal', 'MACD_Signal', 'rsi', 'RSI_14',
        'boll_mid', 'boll_upper', 'boll_lower',
        'chip_bottom_ratio_20d', 'chip_top_ratio_20d', 'chip_stability_20d',
        'momentum',
        'close_lag1', 'close_lag2', 'close_lag3',
        'volume_lag1', 'volume_lag2', 'volume_lag3'
    ]
    features = [f for f in features if f in df.columns]
    return features

def main():
    import os
    model_path = 'xgb_model.json'
    scaler_path = 'scaler.pkl'
    # 1. 原始数据
    if os.path.exists('1_raw_data.csv'):
        stock_data = pd.read_csv('1_raw_data.csv')
        print('已加载 1_raw_data.csv')
    else:
        print("获取本地通达信股票列表...")
        stock_list = get_stock_list()
        print(f"股票数: {len(stock_list)}")
        all_data = []
        for symbol in stock_list:
            data = get_local_data(symbol)
            if data is not None:
                all_data.append(data)
        if not all_data:
            print("未获取到任何股票数据")
            return
        stock_data = pd.concat(all_data, ignore_index=True)
        print("原始数据维度:", stock_data.shape)
        stock_data.to_csv('1_raw_data.csv', index=False, encoding='utf-8-sig')
    # 2. 预处理
    if os.path.exists('2_preprocessed_data.csv'):
        stock_data = pd.read_csv('2_preprocessed_data.csv')
        print('已加载 2_preprocessed_data.csv')
    else:
        stock_data = preprocess_data(stock_data)
        print("预处理后数据维度:", stock_data.shape)
        stock_data.to_csv('2_preprocessed_data.csv', index=False, encoding='utf-8-sig')
    # 3. 技术指标
    if os.path.exists('3_tech_data.csv'):
        tech_data = pd.read_csv('3_tech_data.csv')
        print('已加载 3_tech_data.csv')
    else:
        print("计算技术指标...")
        tech_data = calculate_technical_features(stock_data)
        tech_data.to_csv('3_tech_data.csv', index=False, encoding='utf-8-sig')
    # 4. 标签
    if os.path.exists('4_labeled_data.csv'):
        labeled_data = pd.read_csv('4_labeled_data.csv')
        print('已加载 4_labeled_data.csv')
    else:
        print("准备标签...")
        labeled_data = prepare_labels(tech_data)
        labeled_data = labeled_data.dropna()
        print("最终可用数据维度:", labeled_data.shape)
        labeled_data.to_csv('4_labeled_data.csv', index=False, encoding='utf-8-sig')
    features = feature_selection(labeled_data)
    X = labeled_data[features]
    y = labeled_data['label']
    # 判断模型文件是否存在
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        print('已加载模型和scaler')
        model = xgb.Booster()
        model.load_model(model_path)
        scaler = joblib.load(scaler_path)
    else:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=features, index=X.index)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        print(f"训练集样本数: {len(X_train)} 测试集样本数: {len(X_test)}")
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dtest = xgb.DMatrix(X_test, label=y_test)
        params = {
            'objective': 'reg:squarederror',
            'eval_metric': 'rmse',
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
        preds = model.predict(dtest)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        print(f"测试集RMSE: {rmse:.6f}")
        print("\n特征重要性:")
        xgb.plot_importance(model, max_num_features=15)
        plt.tight_layout()
        plt.savefig('feature_importance.png')
        plt.close()
        print('特征重要性已保存为 feature_importance.png')
        # 保存模型和scaler
        model.save_model(model_path)
        joblib.dump(scaler, scaler_path)
        print('模型和scaler已保存')
    # 预测部分
    X_scaled = scaler.transform(X)
    X = pd.DataFrame(X_scaled, columns=features, index=X.index)
    today = datetime.datetime.now().strftime('%Y%m%d')
    print('DEBUG: today =', today)
    print('DEBUG: labeled_data["date"] min =', labeled_data['date'].min())
    print('DEBUG: labeled_data["date"] max =', labeled_data['date'].max())
    print('DEBUG: labeled_data["date"] nunique =', labeled_data['date'].nunique())
    print('DEBUG: labeled_data["date"] last 10 unique =', labeled_data['date'].drop_duplicates().sort_values().unique()[-10:])
    today_data = labeled_data[labeled_data['date'] == today]
    print('DEBUG: today_data.shape =', today_data.shape)
    if not today_data.empty:
        dcurrent = xgb.DMatrix(today_data[features])
        predictions = model.predict(dcurrent)
        today_data = today_data.assign(prediction=predictions)
        today_data['预测涨跌幅(%)'] = (today_data['prediction'] * 100).round(2)
        selected = today_data.nlargest(20, 'prediction')
        print("\n今日预测未来5日收益率最高的股票：")
        print(selected[['ts_code', 'date', 'close', 'prediction', '预测涨跌幅(%)']])
    else:
        last_date = labeled_data['date'].max()
        print('DEBUG: fallback last_date =', last_date)
        today_data = labeled_data[labeled_data['date'] == last_date]
        print('DEBUG: fallback today_data.shape =', today_data.shape)
        dcurrent = xgb.DMatrix(today_data[features])
        predictions = model.predict(dcurrent)
        today_data = today_data.assign(prediction=predictions)
        today_data['预测涨跌幅(%)'] = (today_data['prediction'] * 100).round(2)
        selected = today_data.nlargest(20, 'prediction')
        print(f"\n使用最新数据({last_date})预测未来5日收益率最高的股票：")
        print(selected[['ts_code', 'date', 'close', 'prediction', '预测涨跌幅(%)']])

if __name__ == "__main__":
    main()