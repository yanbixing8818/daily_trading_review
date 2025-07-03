import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
import baostock as bs
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# ================== 1. 数据获取与预处理 ==================
def fetch_stock_data(stock_code, years=3):
    """
    获取股票历史数据（支持A股/美股）
    :param stock_code: 股票代码（如'AAPL'或'600519.SS'）
    :param years: 数据年份
    :return: DataFrame格式的历史数据
    """
    end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    start_date = (pd.Timestamp.now() - pd.DateOffset(years=years)).strftime('%Y-%m-%d')

    def add_prefix(code):
        code = str(code)
        if code.startswith(('6', '9')):
            return 'sh.' + code[:6]
        elif code.startswith(('0', '3', '2')):
            return 'sz.' + code[:6]
        else:
            return code  # 若无法识别则原样返回

    def get_a_hist_k_data(baostock_code, start_date, end_date):
        # 登陆系统
        lg = bs.login()
        # 查询历史K线数据
        rs = bs.query_history_k_data_plus(
            baostock_code,
            "date,code,open,high,low,close,volume,amount,adjustflag",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="2")
        # 获取具体的信息
        result_list = []
        while (rs.error_code == '0') & rs.next():
            result_list.append(rs.get_row_data())
        result = pd.DataFrame(result_list, columns=rs.fields)
        # 登出系统
        bs.logout()
        # 转换数据类型
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            result[col] = pd.to_numeric(result[col], errors='coerce')
        result['date'] = pd.to_datetime(result['date'])
        # 兼容特征工程字段
        result = result.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'amount': 'Amount',
            'date': 'Date',
        })
        result.set_index('Date', inplace=True)
        result['Stock'] = baostock_code
        return result

    # 判断A股还是美股
    if stock_code.endswith('.SS') or stock_code.endswith('.SZ'):
        # A股，转为baostock格式
        code = stock_code.replace('.SS', '').replace('.SZ', '')
        baostock_code = add_prefix(code)
        try:
            data = get_a_hist_k_data(baostock_code, start_date, end_date)
            print(f"成功用baostock获取{stock_code}近{years}年数据，共{len(data)}条")
            return data
        except Exception as e:
            print(f"baostock数据获取失败: {e}")
            return None
    else:
        # 美股等用yfinance
        try:
            data = yf.download(stock_code, start=start_date, end=end_date)
            data['Stock'] = stock_code  # 添加股票标识
            print(f"成功用yfinance获取{stock_code}近{years}年数据，共{len(data)}条")
            return data
        except Exception as e:
            print(f"yfinance数据获取失败: {e}")
            return None

# ================== 2. 竞价特征工程 ==================
def create_bidding_features(data):
    """
    生成竞价相关特征（结合技术指标与量价关系）
    :param data: 原始行情数据
    :return: 带特征标签的DataFrame
    """
    df = data.copy()
    
    # 基础特征
    df['Open_Change'] = df['Open'] / df['Close'].shift(1) - 1  # 竞价涨跌幅[1](@ref)
    df['Volume_Ratio'] = df['Volume'] / df['Volume'].rolling(5).mean()  # 量比[4](@ref)
    
    # 技术指标
    df['RSI_14'] = compute_rsi(df['Close'], 14)  # 相对强弱指数
    df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
    df['Bollinger_Width'] = (df['Close'].rolling(20).std() * 2) / df['Close'].rolling(20).mean()  # 布林带宽度
    
    # 目标变量：次日涨幅>3%标记为1（可调整阈值）
    df['Target'] = np.where(df['Close'].shift(-1) > df['Close'] * 1.03, 1, 0)
    
    df.dropna(inplace=True)
    return df

def compute_rsi(series, window=14):
    """计算RSI指标"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================== 3. 模型训练与评估 ==================
def train_random_forest(X_train, y_train):
    """
    训练随机森林分类器（带防过拟合配置）
    :return: 训练好的模型
    """
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,               # 限制树深度[6](@ref)
        min_samples_split=10,       # 减少过拟合风险
        max_features='sqrt',        # 特征随机性[8](@ref)
        class_weight='balanced',    # 处理涨跌样本不平衡
        random_state=42
    )
    model.fit(X_train, y_train)
    return model

# ================== 4. 竞价选股预测 ==================
def predict_bidding_stocks(model, scaler, current_data):
    """
    基于当日竞价数据生成选股信号
    :return: 买入概率（0-1）
    """
    current_features = create_bidding_features(current_data).iloc[-1:]
    X_current = current_features.drop(['Target', 'Stock', 'code', 'adjustflag'], axis=1, errors='ignore')
    X_scaled = scaler.transform(X_current)
    return model.predict_proba(X_scaled)[0][1]  # 返回上涨概率

# ================== 主程序 ==================
if __name__ == "__main__":
    # 自动获取沪深300成分股
    def get_hs300_yf_codes():
        lg = bs.login()
        rs = bs.query_hs300_stocks()
        stocks = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            code = row[1]  # 股票代码
            # 转为yfinance格式
            if code.startswith('6'):
                stocks.append(code + '.SS')
            else:
                stocks.append(code + '.SZ')
        bs.logout()
        return stocks

    stock_pool = get_hs300_yf_codes()
    print(f"沪深300成分股数量: {len(stock_pool)}")
    selected_stocks = []
    
    for stock in stock_pool:
        # 1. 获取数据
        raw_data = fetch_stock_data(stock, years=3)
        if raw_data is None: continue
        
        # 2. 特征工程
        featured_data = create_bidding_features(raw_data)
        
        # 3. 数据预处理
        X = featured_data.drop(['Target', 'Stock', 'code', 'adjustflag'], axis=1, errors='ignore')
        # 检查所有特征列类型
        non_numeric_cols = X.select_dtypes(include=['object']).columns.tolist()
        if non_numeric_cols:
            raise ValueError(f"特征列中包含非数值型字段: {non_numeric_cols}，请检查数据处理流程！")
        y = featured_data['Target']
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # 4. 时间序列分割（避免前瞻偏差）
        tscv = TimeSeriesSplit(n_splits=3)
        for train_idx, test_idx in tscv.split(X_scaled):
            X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # 5. 训练模型
            model = train_random_forest(X_train, y_train)
            
            # 6. 评估模型（测试集）
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            print(f"{stock}模型准确率: {accuracy:.2f}")
        
        # 7. 模拟当日竞价数据
        current_data = fetch_stock_data(stock, years=1).iloc[-30:]  # 最近30天
        
        # 8. 预测并记录高概率股票
        buy_prob = predict_bidding_stocks(model, scaler, current_data)
        if buy_prob > 0.65:  # 概率阈值
            selected_stocks.append((stock, buy_prob))
    
    # 9. 输出选股结果
    print("\n===== 推荐买入股票 =====")
    for stock, prob in selected_stocks:
        print(f"{stock}: 上涨概率{prob:.2%}")
    
    # 10. 特征重要性分析（可视化）
    plt.figure(figsize=(10, 6))
    importance = pd.Series(model.feature_importances_, index=X.columns)
    importance.sort_values().plot(kind='barh', color='#3498db')
    plt.title('随机森林特征重要性', fontsize=14)
    plt.xlabel('重要性得分', fontsize=12)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('feature_importance.png')