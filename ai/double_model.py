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

# 配置日志和参数
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {
    'tdx_path': '/mnt/c/new_tdx',      # 通达信数据目录
    'model_dir': 'models',         # 模型保存目录
    'data_days': 60,               # 历史数据天数
    'test_size': 0.2,              # 测试集比例
    'top_n': 10,                   # 每日选股数量
    'fusion_weights': (0.4, 0.6)  # XGBoost和LightGBM融合权重
}

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
                    code.startswith(('600', '601', '603', '605')) or
                    code.startswith('688') or
                    code.startswith(('000', '001', '002', '003')) or
                    code.startswith(('300', '301')) or
                    code.startswith(('83', '87'))
                ):
                    code_set.add(fname)
    code_list = sorted(code_set)
    logger.info(f"本地A股代码数: {len(code_list)}")
    return code_list

def get_local_data(symbol, days=CONFIG['data_days']):
    """
    获取本地日线数据（只用daily_data做特征工程，避免多列close冲突）
    """
    try:
        reader = Reader.factory(market='std', tdxdir=CONFIG['tdx_path'])
        # 获取日线数据
        daily_data = reader.daily(symbol=symbol)
        if daily_data is None or len(daily_data) < days:
            return None
        return daily_data.tail(days)
    except Exception as e:
        logger.error(f"获取{symbol}数据失败: {str(e)}")
        return None

def calculate_features(df):
    """
    计算技术指标特征[6,9](@ref)
    包含竞价特征和技术指标
    """
    try:
        # 基础价格特征
        df['ret_1d'] = df['close'].pct_change()
        df['volatility_5d'] = df['close'].pct_change().rolling(5).std()
        
        # 均线系统
        df['MA_5'] = talib.MA(df['close'], timeperiod=5)
        df['MA_10'] = talib.MA(df['close'], timeperiod=10)
        df['MA_20'] = talib.MA(df['close'], timeperiod=20)
        
        # MACD指标
        macd, macdsignal, _ = talib.MACD(df['close'])
        df['MACD'] = macd
        df['MACD_Signal'] = macdsignal
        
        # RSI指标
        df['RSI_14'] = talib.RSI(df['close'], timeperiod=14)
        
        # 竞价特征部分：
        # 如果数据中包含'pre_open'这一列，说明有集合竞价的开盘价和成交量信息。
        # pre_open_change 计算今日集合竞价开盘价相对于昨日收盘价的涨跌幅。
        # pre_volume_ratio 计算集合竞价成交量与最近5日平均日成交量的比值，衡量竞价活跃度。
        if 'pre_open' in df.columns:
            df['pre_open_change'] = (df['pre_open'] - df['close'].shift(1)) / df['close'].shift(1)
            df['pre_volume_ratio'] = df['pre_volume'] / df['volume'].rolling(5).mean()
        # 目标变量：未来3日涨幅超过5%
        df['target'] = (df['close'].shift(-3) / df['close'] - 1 > 0.05).astype(int)
        
        return df.dropna()
    except Exception as e:
        logger.error(f"特征计算失败: {str(e)}")
        return None

def prepare_dataset(stock_list):
    """
    遍历股票池，读取本地日线数据，计算特征，拼接训练集。
    - 对每只股票，先用get_local_data(symbol)读取日线数据
    - 用calculate_features(data)计算技术指标和目标变量
    - 丢弃无数据或特征为空的股票
    - 拼接所有股票的特征和标签到X、y
    - 用StandardScaler做归一化
    - 返回归一化特征、标签和scaler
    """
    X, y = [], []
    
    for symbol in stock_list:  # 遍历所有股票
        data = get_local_data(symbol)
        if data is None:
            print(f"{symbol} 无本地数据")
            continue
        data_with_features = calculate_features(data)
        if data_with_features is None or data_with_features.empty:
            print(f"{symbol} 特征为空")
            continue
        # 排除目标列
        features = data_with_features.drop(['target'], axis=1).values
        targets = data_with_features['target'].values
        X.extend(features)
        y.extend(targets)
        # logger.info(f"处理完成: {symbol}")
    print(f"最终特征样本数: {len(X)}")
    # 数据标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    return X_scaled, np.array(y), scaler

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
    """每日竞价选股[3,5](@ref)"""
    today = datetime.now().strftime("%Y-%m-%d")
    selected_stocks = []
    stock_list = get_stock_list()
    
    for symbol in stock_list:
        data = get_local_data(symbol)
        if data is None or len(data) < 5:
            continue
        
        # 计算特征
        latest_data = calculate_features(data).iloc[-1:].drop(['target'], axis=1)
        if latest_data.empty:
            continue
        
        # 数据标准化
        X_scaled = scaler.transform(latest_data.values)
        
        # 模型预测
        xgb_proba = models[0].predict_proba(X_scaled)[0][1]
        lgb_proba = models[1].predict(X_scaled)[0]
        
        # 加权融合预测概率[14](@ref)
        fused_proba = (CONFIG['fusion_weights'][0] * xgb_proba + 
                       CONFIG['fusion_weights'][1] * lgb_proba)
        
        selected_stocks.append({
            'symbol': symbol,
            'probability': fused_proba,
            'pre_open': data.iloc[-1]['open'],
            'last_close': data.iloc[-2]['close'],
            'pre_change': (data.iloc[-1]['open'] / data.iloc[-2]['close'] - 1) * 100
        })
    
    # 按概率排序取前N
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
    plt.xticks(range(len(importances)), np.array(feature_names)[indices], rotation=90)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    logger.info(f"{model_type.upper()}特征重要性已保存到 {filename}")

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
        # 由于特征名未保存，尝试从train_features.csv读取
        feature_df = pd.read_csv('train_features.csv')
        feature_names = feature_df.columns[:-1]  # 最后一列是label
    else:
        logger.info("训练新模型")
        stock_list = get_stock_list()
        X, y, scaler = prepare_dataset(stock_list)
        # 保存特征数据到csv
        feature_df = pd.DataFrame(X)
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
    main()