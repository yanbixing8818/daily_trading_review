import os
import pandas as pd
import numpy as np
from mootdx.reader import Reader
from mootdx.quotes import Quotes
import joblib
import xgboost as xgb
import lightgbm as lgb
from test_xgmodel import feature_selection, calculate_technical_features, fused_predict, FACTOR_SWITCHES
from test_xgmodel import get_stock_list
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
history_csv = os.path.join(BASE_DIR, '2_tech_data.csv')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
TDX_PATH = '/mnt/c/new_tdx'

def get_realtime_stock_data(stock_list, tdx_path=TDX_PATH):
    """
    实时获取指定股票列表的行情数据（只取最新一条）
    """
    quotes = Quotes.factory(market='std', tdxdir=tdx_path)
    batch_size = 80
    all_data = []
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i:i+batch_size]
        try:
            df = quotes.quotes(symbol=batch)
            if df is not None and not df.empty:
                all_data.append(df)
        except Exception as e:
            print(f"实时行情获取失败: {e}")
    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)
        # 兼容字段
        def market_code_to_prefix(market):
            if str(market) == '0':
                return 'sz'
            elif str(market) == '1':
                return 'sh'
            else:
                return ''
        if 'code' in df_all.columns and 'market' in df_all.columns:
            df_all['ts_code'] = df_all.apply(lambda row: market_code_to_prefix(row['market']) + str(row['code']).zfill(6), axis=1)
        # 字段标准化
        if 'price' in df_all.columns:
            df_all['close'] = df_all['price']
        if 'last_close' in df_all.columns:
            df_all['pre_close'] = df_all['last_close']
        if 'open' in df_all.columns:
            df_all['open'] = df_all['open']
        if 'high' in df_all.columns:
            df_all['high'] = df_all['high']
        if 'low' in df_all.columns:
            df_all['low'] = df_all['low']
        if 'volume' in df_all.columns:
            df_all['volume'] = df_all['volume']
        print('[DEBUG] 实时行情字段:', list(df_all.columns))
        print('[DEBUG] 实时行情前5行:')
        print(df_all.head())
        return df_all
    return pd.DataFrame()

def load_models_and_scalers():
    xgb_model = xgb.Booster()
    xgb_model.load_model(os.path.join(MODELS_DIR, 'xgb_model.json'))
    xgb_scaler = joblib.load(os.path.join(MODELS_DIR, 'xgb_scaler.pkl'))
    lgb_model = lgb.Booster(model_file=os.path.join(MODELS_DIR, 'lgb_model.txt'))
    lgb_scaler = joblib.load(os.path.join(MODELS_DIR, 'lgb_scaler.pkl'))
    return xgb_model, xgb_scaler, lgb_model, lgb_scaler

def main():
    # 默认流程：读取历史特征数据和实时行情，拼接后重算指标并推理
    print(f'读取历史特征数据: {history_csv}')
    hist_df = pd.read_csv(history_csv)
    stock_list = get_stock_list()
    print(f'实时预测股票数: {len(stock_list)}')
    realtime_df = get_realtime_stock_data(stock_list)
    if realtime_df.empty:
        print('未获取到实时行情数据')
        return
    realtime_df['date'] = pd.to_datetime('today').strftime('%Y%m%d')
    # 字段标准化
    if 'price' in realtime_df.columns:
        realtime_df['close'] = realtime_df['price']
    if 'last_close' in realtime_df.columns:
        realtime_df['pre_close'] = realtime_df['last_close']
    if 'open' in realtime_df.columns:
        realtime_df['open'] = realtime_df['open']
    if 'high' in realtime_df.columns:
        realtime_df['high'] = realtime_df['high']
    if 'low' in realtime_df.columns:
        realtime_df['low'] = realtime_df['low']
    if 'volume' in realtime_df.columns:
        realtime_df['volume'] = realtime_df['volume']
    # 适配ts_code格式为sz301268等
    def convert_ts_code(code):
        code = str(code)
        # 如果是7位且0开头，去掉前导0
        if len(code) == 7 and code.startswith('0'):
            code = code[1:]
        if len(code) == 6 and code.startswith('6'):
            return 'sh' + code
        elif len(code) == 6 and code.startswith(('0', '3')):
            return 'sz' + code
        return code
    if 'ts_code' in realtime_df.columns:
        realtime_df['ts_code'] = realtime_df['ts_code'].apply(convert_ts_code)
    # 拼接历史和今天
    all_df = pd.concat([hist_df, realtime_df], ignore_index=True, sort=False)
    all_df['date'] = pd.to_datetime(all_df['date'], errors='coerce')
    all_df.to_csv('debug_all_df_before_features.csv', index=False, encoding='utf-8-sig')
    # 重新计算所有技术指标
    all_df = calculate_technical_features(all_df, factor_switches=FACTOR_SWITCHES)
    all_df.to_csv('debug_all_df_after_features.csv', index=False, encoding='utf-8-sig')
    today_str = pd.to_datetime('today').strftime('%Y%m%d')
    today_df = all_df[all_df['date'] == pd.to_datetime(today_str)]
    today_df.to_csv('debug_today_df_before_pred.csv', index=False, encoding='utf-8-sig')
    features = feature_selection(today_df)
    print('[DEBUG] features:', features)
    print('[DEBUG] today_df.shape:', today_df.shape)
    # 处理inf和nan
    today_df[features] = today_df[features].replace([np.inf, -np.inf], np.nan)
    today_df[features] = today_df[features].fillna(0)
    today_df.to_csv('debug_today_df_for_pred.csv', index=False, encoding='utf-8-sig')
    xgb_model, xgb_scaler, lgb_model, lgb_scaler = load_models_and_scalers()
    features_scaled_xgb = xgb_scaler.transform(today_df[features])
    features_scaled_lgb = lgb_scaler.transform(today_df[features])
    dcurrent = xgb.DMatrix(features_scaled_xgb, feature_names=features)
    xgb_proba = xgb_model.predict(dcurrent)
    lgb_proba = lgb_model.predict(features_scaled_lgb)
    fused_proba = 0.5 * xgb_proba + 0.5 * lgb_proba
    today_df = today_df.assign(xgb_proba=xgb_proba, lgb_proba=lgb_proba, probability=fused_proba)
    today_df['预测明日大涨10%概率(%)'] = (today_df['probability'] * 100).round(2)
    today_df.to_csv('debug_today_df_with_pred.csv', index=False, encoding='utf-8-sig')
    # 补全name字段，直接用stock_name_mapping.csv
    try:
        name_map_path = os.path.join(BASE_DIR, '../base_data/stock_name_mapping.csv')
        if not os.path.exists(name_map_path):
            name_map_path = os.path.join(BASE_DIR, 'base_data/stock_name_mapping.csv')
        name_map_df = pd.read_csv(name_map_path)
        name_map = name_map_df.set_index('ts_code')['name']
        today_df['name'] = today_df.apply(lambda row: name_map.get(row['ts_code'], row['name']), axis=1)
    except Exception as e:
        print('[DEBUG] 用stock_name_mapping.csv补全name失败:', e)
    selected = today_df.nlargest(20, 'probability')
    print('\n基于历史+实时数据，预测创业板明日大涨10%概率最高的股票：')
    print(selected[['ts_code', 'name', 'close', '预测明日大涨10%概率(%)']])
    print('今日实时推理结果已保存到 debug_today_df_with_pred.csv')

if __name__ == '__main__':
    main()
