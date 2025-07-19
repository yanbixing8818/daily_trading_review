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
from sklearn.model_selection import TimeSeriesSplit

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

def make_attack_label(df, high_window=60, vol_window=20, ma_window=60, vol_ratio=1.5, future_days=5, future_thresh=0.05):
    df = df.copy()
    # 1. 新高
    df['is_new_high'] = df['close'] == df['close'].rolling(high_window).max()
    # 2. 均线多头排列
    df['ma5'] = df.groupby('ts_code')['close'].transform(lambda x: talib.MA(x, timeperiod=5))
    df['ma10'] = df.groupby('ts_code')['close'].transform(lambda x: talib.MA(x, timeperiod=10))
    df['ma20'] = df.groupby('ts_code')['close'].transform(lambda x: talib.MA(x, timeperiod=20))
    df['ma60'] = df.groupby('ts_code')['close'].transform(lambda x: talib.MA(x, timeperiod=ma_window))
    df['multi_ma'] = (df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20']) & (df['ma20'] > df['ma60'])
    # 3. 放量突破60日线
    df['ma60_cross'] = (df['close'] > df['ma60']) & (df['close'].shift(1) <= df['ma60'].shift(1))
    df['vol_ma20'] = df.groupby('ts_code')['volume'].transform(lambda x: x.rolling(vol_window).mean())
    df['vol_break'] = df['volume'] > df['vol_ma20'] * vol_ratio
    # 4. 未来5日涨幅
    df['future_return'] = df.groupby('ts_code')['close'].transform(lambda x: x.shift(-future_days) / x - 1)
    # 5. 进攻型标签
    df['attack_label'] = (
        df['is_new_high'] |
        df['multi_ma'] |
        df['ma60_cross'] |
        df['vol_break'] |
        (df['future_return'] > future_thresh)
    ).astype(int)
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
        # 只保留2024年9月1日及以后的数据
        stock_data = stock_data[stock_data['date'] >= '20240901']
        print("筛选后数据维度:", stock_data.shape)
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
    # 4. 标签（进攻型）
    print("生成进攻型标签...")
    labeled_data = make_attack_label(tech_data)
    labeled_data = labeled_data.dropna()
    labeled_data.to_csv('4_labeled_data.csv', index=False, encoding='utf-8-sig')
    # 只在attack_label=1的样本上做回归
    attack_data = labeled_data[labeled_data['attack_label'] == 1].copy()
    print(f"进攻型样本数: {len(attack_data)}")
    features = feature_selection(attack_data)
    X = attack_data[features]
    y = attack_data['future_return']
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
        tscv = TimeSeriesSplit(n_splits=5)
        best_rmse = float('inf')
        best_model = None
        for fold, (train_index, test_index) in enumerate(tscv.split(X)):
            print(f"Fold {fold+1}")
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
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
            print(f"Fold {fold+1} RMSE: {rmse:.6f}")
            score = model.get_score(importance_type='weight')
            print('特征重要性字典:', score)
            if not score:
                print('警告：模型未能分裂出有效特征，可能是样本太少或特征无效。')
            if fold == tscv.n_splits - 1:
                # 只保存最后一折的特征重要性图和模型
                if score:
                    xgb.plot_importance(model, max_num_features=15)
                    plt.tight_layout()
                    plt.savefig('feature_importance.png')
                    plt.close()
                    print('特征重要性已保存为 feature_importance.png')
                best_model = model
                best_rmse = rmse
        # 保存最后一折的模型和scaler
        best_model.save_model(model_path)
        joblib.dump(scaler, scaler_path)
        print(f'模型和scaler已保存（最后一折RMSE: {best_rmse:.6f}）')
        model = best_model

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
        # 回测评估（仅当有future_return时）
        if 'future_return' in selected.columns:
            print('\n回测评估指标:')
            evaluate_backtest(selected)
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
        # 回测评估（仅当有future_return时）
        if 'future_return' in selected.columns:
            print('\n回测评估指标:')
            evaluate_backtest(selected)

if __name__ == "__main__":
    main()