import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
import os
import joblib
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
import re
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from test_xgmodel import train_xgb, train_lightgbm

JINGJIA_BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jingjia_base_data')
JINGJIA_FEATURES = [
    '竞价涨幅', '竞价匹配价', '竞价量', '分时换手率', '分时量比', '竞价金额', 
    '竞价未匹配量', '竞价未匹配金额', 'a股市值(不含限售股)', '小单净额', 
    '竞价异动类型', '竞价异动说明', '集合竞价评级', '分时成交量'
]

JINGJIA_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jingjia_models')
os.makedirs(JINGJIA_MODELS_DIR, exist_ok=True)

def safe_feature_name(name):
    # 替换所有非中英文、数字、下划线为下划线
    return re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', name)

def normalize_bidding_columns(df):
        # 去掉列名中的 [YYYYMMDD HH:MM(:SS)]，并合并因此产生的重复列（逐行取非空优先）
        df = df.copy()
        orig_cols = list(df.columns)
        pattern = r"\[\d{8}\s\d{2}:\d{2}(?::\d{2})?\]"
        new_cols = [re.sub(pattern, '', c) for c in orig_cols]
        df.columns = new_cols
        # 合并重复列：按位置索引分组，逐行bfill取首个非空值
        from collections import defaultdict
        name_to_positions = defaultdict(list)
        for pos, name in enumerate(new_cols):
            name_to_positions[name].append(pos)
        cols_to_drop = []
        for name, positions in name_to_positions.items():
            if len(positions) > 1:
                merged = df.iloc[:, positions].bfill(axis=1).iloc[:, 0]
                df.iloc[:, positions[0]] = merged
                # 记录除第一个外的重复列名用于删除
                cols_to_drop.extend([df.columns[p] for p in positions[1:]])
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
        return df

def load_jingjia_data():
    import glob
    import re

    all_files = glob.glob(os.path.join(JINGJIA_BASE_DATA_DIR, 'bidding_data_*.csv'))
    dfs = []
    for f in all_files:
        df = pd.read_csv(f)
        # 标准化动态时间列
        df = normalize_bidding_columns(df)
        date_str = os.path.basename(f).replace('bidding_data_', '').replace('.csv', '')
        df['date'] = date_str
        dfs.append(df)
    if not dfs:
        raise RuntimeError('未找到任何竞价数据文件')
    all_data = pd.concat(dfs, ignore_index=True)
    # 保存中间结果
    out_path = os.path.join(JINGJIA_BASE_DATA_DIR, 'bidding_all_data.csv')
    all_data.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"合并竞价数据文件数: {len(dfs)}, 总样本数: {len(all_data)}。已保存到 {out_path}")
    return all_data

def feature_selection_jingjia(df):
    # 先重命名DataFrame的列
    rename_map = {col: safe_feature_name(col) for col in df.columns}
    df.rename(columns=rename_map, inplace=True)
    
    # 更新特征列表，使用安全的特征名
    safe_features = [safe_feature_name(f) for f in JINGJIA_FEATURES]
    print(f"原始特征: {JINGJIA_FEATURES}")
    print(f"安全特征名: {safe_features}")
    
    # 检查哪些特征在数据中存在
    available_features = [f for f in safe_features if f in df.columns]
    missing_features = [f for f in safe_features if f not in df.columns]
    
    print(f"可用特征: {available_features}")
    if missing_features:
        print(f"缺失特征: {missing_features}")
    
    # 处理分类特征编码
    df_encoded = df.copy()
    categorical_features = []
    
    for feature in available_features:
        if feature in df_encoded.columns:
            # 检查是否为分类特征（字符串类型）
            if df_encoded[feature].dtype == 'object' or df_encoded[feature].dtype == 'string':
                print(f"编码分类特征: {feature}")
                categorical_features.append(feature)
                # 使用LabelEncoder进行编码
                from sklearn.preprocessing import LabelEncoder
                le = LabelEncoder()
                # 处理NaN值
                df_encoded[feature] = df_encoded[feature].fillna('未知')
                # 编码
                df_encoded[feature] = le.fit_transform(df_encoded[feature].astype(str))
                print(f"  {feature} 编码完成，唯一值: {df_encoded[feature].unique()}")
    
    if categorical_features:
        print(f"已编码的分类特征: {categorical_features}")
    
    # 数据清洗：处理无穷大值和异常值
    print("开始数据清洗...")
    for feature in available_features:
        if feature in df_encoded.columns and feature not in categorical_features:
            # 只处理数值型特征
            if df_encoded[feature].dtype in ['float64', 'int64']:
                # 替换无穷大值
                df_encoded[feature] = df_encoded[feature].replace([np.inf, -np.inf], np.nan)
                
                # 计算分位数，用于异常值处理
                q1 = df_encoded[feature].quantile(0.01)
                q99 = df_encoded[feature].quantile(0.99)
                
                # 将异常值替换为分位数边界值
                df_encoded[feature] = df_encoded[feature].clip(lower=q1, upper=q99)
                
                # 填充剩余的NaN值
                df_encoded[feature] = df_encoded[feature].fillna(df_encoded[feature].median())
                
                print(f"  {feature}: 处理完成，范围: [{df_encoded[feature].min():.4f}, {df_encoded[feature].max():.4f}]")
    
    # 最终检查：确保没有无穷大值或NaN
    for feature in available_features:
        if feature in df_encoded.columns:
            if df_encoded[feature].dtype in ['float64', 'int64']:
                if np.any(np.isinf(df_encoded[feature])) or np.any(np.isnan(df_encoded[feature])):
                    print(f"警告: {feature} 仍包含无效值")
                    # 最后的安全处理
                    df_encoded[feature] = df_encoded[feature].replace([np.inf, -np.inf], 0)
                    df_encoded[feature] = df_encoded[feature].fillna(0)
    
    print("数据清洗完成")
    return available_features, df_encoded

def create_target(df, thresh=0.15):
    df = df.copy()
    # 目标设定为：当日收盘价相对于昨日收盘价涨幅>=15%为正样本
    if '收盘价' in df.columns:
        df['prev_close'] = df.groupby('股票代码')['收盘价'].shift(1)
        df['pct_chg'] = (df['收盘价'] / df['prev_close'] - 1)
        df['target'] = (df['pct_chg'] >= thresh).astype(int)
    else:
        raise ValueError('数据中缺少收盘价字段')
    df['sample_weight'] = 1.0
    return df

# 补充：通达信日线收盘价补全逻辑
TDX_PATH = 'E:/new_tdx'  # 按实际路径修改
from mootdx.reader import Reader

def add_close_from_tdx(df, code_col='股票代码', date_col='date'):
    """为竞价数据补充通达信收盘价，兼容date为index的情况"""
    df = df.copy()
    codes = df[code_col].unique()
    reader = Reader.factory(market='std', tdxdir=TDX_PATH)
    close_map = {}
    for code in codes:
        # 代码格式适配
        if code.endswith('.SZ'):
            tdx_code = 'sz' + code[:6]
        elif code.endswith('.SH'):
            tdx_code = 'sh' + code[:6]
        else:
            continue
        try:
            daily = reader.daily(symbol=tdx_code)
            if daily is not None and not daily.empty:
                daily = daily.copy()
                # 兼容date为index的情况
                if 'date' not in daily.columns:
                    if hasattr(daily.index, 'to_timestamp') or isinstance(daily.index, pd.DatetimeIndex):
                        daily['date'] = daily.index.strftime('%Y%m%d')
                    else:
                        daily['date'] = pd.Series(pd.date_range(end=pd.Timestamp.today(), periods=len(daily))).dt.strftime('%Y%m%d').values
                else:
                    daily['date'] = daily['date'].dt.strftime('%Y%m%d')
                for _, row in daily.iterrows():
                    close_map[(code, row['date'])] = row['close']
        except Exception as e:
            print(f"读取{tdx_code}日线失败: {e}")
    def get_close(row):
        key = (row[code_col], str(row[date_col]))
        return close_map.get(key, np.nan)
    df['收盘价'] = df.apply(get_close, axis=1)
    return df

def predict_bidding_file(csv_path, xgb_model_path, lgb_model_path, xgb_scaler_path, lgb_scaler_path):
    """读取指定竞价csv文件，预测当天大涨股票"""
    # 1. 读取数据
    df = pd.read_csv(csv_path)
    print(f"原始数据列名: {list(df.columns)}")
    
    # 2. 标准化列名（与训练时保持一致）
    df = normalize_bidding_columns(df)
    print(f"标准化后的列名: {list(df.columns)}")
    
    # 3. 特征名映射
    features, df = feature_selection_jingjia(df)
    print(f"特征选择后的特征: {features}")
    print(f"特征选择后的列名: {list(df.columns)}")
    
    # 4. 检查模型文件是否存在
    if not all(os.path.exists(p) for p in [xgb_model_path, lgb_model_path, xgb_scaler_path, lgb_scaler_path]):
        print("错误：模型文件不完整，请先运行main()训练模型")
        return None
    
    # 5. 加载模型和scaler
    xgb_model = xgb.Booster()
    xgb_model.load_model(xgb_model_path)
    lgb_model = lgb.Booster(model_file=lgb_model_path)
    xgb_scaler = joblib.load(xgb_scaler_path)
    lgb_scaler = joblib.load(lgb_scaler_path)
    
    # 6. 检查特征匹配
    # 获取训练时的特征名
    try:
        # 尝试从scaler获取特征名
        if hasattr(xgb_scaler, 'feature_names_in_'):
            train_features = xgb_scaler.feature_names_in_
        else:
            # 如果没有feature_names_in_，使用当前的特征列表
            train_features = features
    except:
        train_features = features
    
    print(f"训练时的特征: {train_features}")
    print(f"预测时的特征: {features}")
    
    # 检查特征是否匹配
    missing_features = [f for f in train_features if f not in features]
    extra_features = [f for f in features if f not in train_features]
    
    if missing_features:
        print(f"警告：预测时缺少训练特征: {missing_features}")
        # 为缺失特征添加默认值
        for feature in missing_features:
            df[feature] = 0
            print(f"  为缺失特征 {feature} 添加默认值 0")
    
    if extra_features:
        print(f"警告：预测时有额外特征: {extra_features}")
    
    # 确保特征顺序一致
    final_features = [f for f in train_features if f in df.columns]
    print(f"最终使用的特征: {final_features}")
    
    # 7. 特征缩放
    X = df[final_features]
    X_xgb = xgb_scaler.transform(X)
    X_lgb = lgb_scaler.transform(X)
    
    # 8. 预测
    dmatrix = xgb.DMatrix(X_xgb, feature_names=final_features)
    xgb_proba = xgb_model.predict(dmatrix)
    lgb_proba = lgb_model.predict(X_lgb)
    fused_proba = 0.5 * xgb_proba + 0.5 * lgb_proba
    df['xgb_proba'] = xgb_proba
    df['lgb_proba'] = lgb_proba
    df['fused_proba'] = fused_proba
    
    # 9. 输出概率最高的前10只股票
    selected = df.nlargest(10, 'fused_proba')
    
    # 仅对这10只股票补全名称
    name_map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'base_data/stock_name_mapping.csv')
    if os.path.exists(name_map_path):
        name_map = pd.read_csv(name_map_path)
        def to_ts_code(code):
            code = str(code)
            if code.endswith('.SZ'):
                return 'sz' + code[:6]
            elif code.endswith('.SH'):
                return 'sh' + code[:6]
            elif code.startswith('sz') or code.startswith('sh'):
                return code
            else:
                return code
        def clean_code(code):
            return re.sub(r'[^a-zA-Z0-9]', '', str(code)).strip().lower()
        selected['ts_code'] = selected['股票代码'].map(to_ts_code).map(clean_code)
        name_map['ts_code'] = name_map['ts_code'].map(clean_code)
        selected = pd.merge(selected, name_map[['ts_code', 'name']], on='ts_code', how='left')
        selected['名称'] = selected['name'].fillna('')
    else:
        selected['名称'] = ''
    
    # 更新输出列名，适配新的数据结构
    output_cols = ['股票代码', '名称', 'xgb_proba', 'lgb_proba', 'fused_proba']
    
    # 添加可用的竞价相关列
    available_cols = ['竞价涨幅', '竞价金额', '竞价量', '最新价', '最新涨跌幅', '股票简称']
    for col in available_cols:
        if col in selected.columns and col not in output_cols:
            output_cols.insert(2, col)  # 插入到名称之后
    
    if '名称' not in selected.columns:
        selected['名称'] = ''
    
    print(f"\n{os.path.basename(csv_path)} 预测大涨概率最高的股票：")
    print(selected[output_cols])
    
    return selected[output_cols]

def main():
    model_path = os.path.join(JINGJIA_MODELS_DIR, 'xgb_model.json')
    scaler_path = os.path.join(JINGJIA_MODELS_DIR, 'xgb_scaler.pkl')
    lgb_model_path = os.path.join(JINGJIA_MODELS_DIR, 'lgb_model.txt')
    lgb_scaler_path = os.path.join(JINGJIA_MODELS_DIR, 'lgb_scaler.pkl')
    # 1. 数据加载与初步处理
    stock_data = load_jingjia_data()
    # 1.1 通达信补全收盘价
    out_dir = os.path.dirname(os.path.abspath(__file__))
    stock_data = add_close_from_tdx(stock_data, code_col='股票代码', date_col='date')
    stock_data.to_csv(os.path.join(out_dir, 'jingjia_with_close.csv'), index=False, encoding='utf-8-sig')
    # 2. 特征工程与标签创建
    features, stock_data = feature_selection_jingjia(stock_data)
    print('竞价特征列:', features)
    labeled_data = create_target(stock_data)
    print('样本数:', labeled_data.shape)
    print('正样本比例:', labeled_data['target'].mean())
    print('正样本数:', labeled_data['target'].sum())
    print('负样本数:', (labeled_data['target'] == 0).sum())
    X = labeled_data[features]
    y = labeled_data['target']
    sample_weight = labeled_data['sample_weight']
    # 3. 模型训练 - 使用test_xgmodel.py中的函数
    xgb_model, xgb_scaler = train_xgb(X, y, features, sample_weight, model_path=model_path, scaler_path=scaler_path)
    lgb_model, lgb_scaler = train_lightgbm(X, y, features, sample_weight, model_path=lgb_model_path, scaler_path=lgb_scaler_path)
    # 4. 结果展示（可自定义）
    print('模型训练完成，可进行预测或进一步分析。')

if __name__ == "__main__":
    # main()
    # 示例：预测指定竞价文件
    predict_bidding_file(
        csv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bidding_data_20250814.csv'),
        xgb_model_path=os.path.join(JINGJIA_MODELS_DIR, 'xgb_model.json'),
        lgb_model_path=os.path.join(JINGJIA_MODELS_DIR, 'lgb_model.txt'),
        xgb_scaler_path=os.path.join(JINGJIA_MODELS_DIR, 'xgb_scaler.pkl'),
        lgb_scaler_path=os.path.join(JINGJIA_MODELS_DIR, 'lgb_scaler.pkl')
    )