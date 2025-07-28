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
    '竞价涨幅', '涨跌幅:前复权', '成交量', '换手率', '量比', '竞价量', '竞价金额', '竞价未匹配量', '竞价未匹配金额',
    'dde大单净额', '中单净额', '小单净额', '主力资金流向', 'a股市值(不含限售股)', '涨跌', '振幅', '成交额', '竞价匹配价'
]
JINGJIA_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jingjia_models')
os.makedirs(JINGJIA_MODELS_DIR, exist_ok=True)

def safe_feature_name(name):
    # 替换所有非中英文、数字、下划线为下划线
    return re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', name)

def load_jingjia_data():
    import glob
    all_files = glob.glob(os.path.join(JINGJIA_BASE_DATA_DIR, 'bidding_data_*.csv'))
    dfs = []
    for f in all_files:
        df = pd.read_csv(f)
        date_str = os.path.basename(f).replace('bidding_data_', '').replace('.csv', '')
        df['date'] = date_str
        dfs.append(df)
    if not dfs:
        raise RuntimeError('未找到任何竞价数据文件')
    all_data = pd.concat(dfs, ignore_index=True)
    print(f"合并竞价数据文件数: {len(dfs)}, 总样本数: {len(all_data)}")
    return all_data

def feature_selection_jingjia(df):
    # 先重命名DataFrame的列
    rename_map = {col: safe_feature_name(col) for col in df.columns}
    df.rename(columns=rename_map, inplace=True)
    features = [safe_feature_name(f) for f in JINGJIA_FEATURES if safe_feature_name(f) in df.columns]
    return features, df

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
TDX_PATH = '/mnt/c/new_tdx'  # 按实际路径修改
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
    # 2. 特征名映射
    features, df = feature_selection_jingjia(df)
    # 4. 加载模型和scaler
    xgb_model = xgb.Booster()
    xgb_model.load_model(xgb_model_path)
    lgb_model = lgb.Booster(model_file=lgb_model_path)
    xgb_scaler = joblib.load(xgb_scaler_path)
    lgb_scaler = joblib.load(lgb_scaler_path)
    # 5. 特征缩放
    X = df[features]
    X_xgb = xgb_scaler.transform(X)
    X_lgb = lgb_scaler.transform(X)
    # 6. 预测
    dmatrix = xgb.DMatrix(X_xgb, feature_names=features)
    xgb_proba = xgb_model.predict(dmatrix)
    lgb_proba = lgb_model.predict(X_lgb)
    fused_proba = 0.5 * xgb_proba + 0.5 * lgb_proba
    df['xgb_proba'] = xgb_proba
    df['lgb_proba'] = lgb_proba
    df['fused_proba'] = fused_proba
    # 7. 输出概率最高的前10只股票
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
    output_cols = ['股票代码', '名称', 'xgb_proba', 'lgb_proba', 'fused_proba']
    for col in ['竞价涨幅', '竞价金额', '竞价量']:
        if col in selected.columns and col not in output_cols:
            output_cols.insert(1, col)
    if '名称' not in selected.columns:
        selected['名称'] = ''
    print(f"\n{os.path.basename(csv_path)} 预测大涨概率最高的股票：")
    print(selected[output_cols])

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
        csv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bidding_data_20250725.csv'),
        xgb_model_path=os.path.join(JINGJIA_MODELS_DIR, 'xgb_model.json'),
        lgb_model_path=os.path.join(JINGJIA_MODELS_DIR, 'lgb_model.txt'),
        xgb_scaler_path=os.path.join(JINGJIA_MODELS_DIR, 'xgb_scaler.pkl'),
        lgb_scaler_path=os.path.join(JINGJIA_MODELS_DIR, 'lgb_scaler.pkl')
    )