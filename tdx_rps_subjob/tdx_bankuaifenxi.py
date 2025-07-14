# 通达信板块指数分析
# 1. 提取板块指数代码和名称
# 2. 计算板块指数的两种日涨幅：
#    - change: (close-open)/open*100       //板块的赚钱效应
#    - pct_change: (close/close.shift(1)-1)*100  //板块的真正百分比涨幅 
# 3. 保存中间过程到csv
# 4. 获取每日涨幅前10的板块指数 

#使用方法：需要自己下载通达信的数据后再运行。
# 1. 盘后数据下载：选项->盘后数据下载->日线数据->勾选日线和实时行情数据->开始下载；
# 2. 概念导出：选项->数据导出->板块成分导出->选择导出文件夹->开始导出；
# 3. 将导出的文件放在 tdx_rps_subjob/tdx_bankuaigainian目录下，目前只放：概念板块.txt和行业板块.txt;
# 3. 运行脚本：python3 -m tdx_rps_subjob.tdx_bankuaifenxi


import pandas as pd
import numpy as np
from mootdx.reader import Reader
from datetime import datetime, timedelta
import os
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import glob
from core.trade_time import stock_trade_date, get_previous_trade_date, is_trade_date  # 新增导入
import sys
from mootdx.quotes import Quotes

# 配置参数
CONFIG = {
    'tdx_path': '/mnt/c/new_tdx',  # 通达信安装路径
    'output_file': 'top_plate_indices.csv',  # 输出文件名
    'plate_prefixes': ['880', '885', '886', '887', '399'],  # 板块指数前缀
    'days': 121,  # 分析
    'real_time_server': '119.147.212.81',  # 或你常用的行情服务器IP
    'real_time_port': 7709                 # 通达信标准端口
}

def load_plate_name_mapping(bankuai_dir='tdx_rps_subjob/tdx_bankuaigainian'):
    """
    读取tdx_bankuai目录下所有txt/csv文件，建立板块代码到中文名的映射dict。
    支持文件格式：每行以逗号、制表符或空格分隔，前两列分别为代码和名称。
    """
    mapping = {}
    for file in glob.glob(os.path.join(bankuai_dir, '*')):
        for encoding in ['utf-8', 'gbk']:
            try:
                with open(file, encoding=encoding) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        for sep in [',', '\t', ' ']:
                            if sep in line:
                                parts = line.split(sep)
                                break
                        else:
                            parts = [line]
                        if len(parts) >= 2:
                            code = parts[0].strip()
                            name = parts[1].strip()
                            mapping[code] = name
                break  # 读成功就不再尝试下一个编码
            except Exception as e:
                if encoding == 'gbk':
                    print(f"读取映射文件{file}失败: {e}")
    print(f"已加载板块名称映射数: {len(mapping)}")
    # 调试输出前10个映射
    for k, v in list(mapping.items())[:10]:
        print(f"映射样例: {k} -> {v}")
    for test_code in ['399750', '399850', '880812']:
        print(f"测试key {test_code} 是否在映射表: {test_code in mapping}")
        if test_code in mapping:
            print(f"{test_code} -> {mapping[test_code]}")
    return mapping

def get_plate_indices():
    """
    从本地通达信目录提取板块指数代码和名称，适配如 sh880793.day 这种文件名格式。
    返回格式：symbol（如sh880793）、name（优先用映射表，否则用代码）
    排除8800开头的板块。
    """
    tdx_path = CONFIG['tdx_path']
    code_set = set()
    # 加载板块名称映射
    name_mapping = load_plate_name_mapping('tdx_rps_subjob/tdx_bankuaigainian')
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(tdx_path, f'vipdoc/{market}/lday')
        if not os.path.exists(lday_dir):
            continue
        files = [f for f in os.listdir(lday_dir) if f.endswith('.day')]
        for fname in files:
            if fname.startswith(market):
                code = fname.replace('.day', '')  # sh880793
                for prefix in CONFIG['plate_prefixes']:
                    if code[len(market):].startswith(prefix) and not code[len(market):].startswith('8800'):
                        code_no_prefix = code[2:] if code.startswith(('sh', 'sz')) else code
                        name = name_mapping.get(code_no_prefix, None)
                        if name is None:
                            print(f"未找到中文名: code={code}, code_no_prefix={code_no_prefix}")
                            break  # 跳过未找到中文名的板块
                        print(f"get_plate_indices: code={code}, code_no_prefix={code_no_prefix}, name={name}")
                        code_set.add((code, name))
                        break
    plate_indices = pd.DataFrame(list(code_set), columns=['code', 'name'])
    print(f"找到{len(plate_indices)}个符合条件的板块指数")
    return plate_indices

def calculate_both_changes(reader, plate_indices):
    """
    计算板块指数的两种日涨幅：
    - change: (close-open)/open*100
    - pct_change: (close/close.shift(1)-1)*100
    合并为一张表，保存中间过程到csv。
    只分析真实交易日。
    """
    all_trade_dates = stock_trade_date().get_data()
    if all_trade_dates is None:
        print("无法获取交易日历")
        return pd.DataFrame()
    # 先统计所有板块指数数据中实际出现过的所有日期
    all_dates_in_data = set()
    for _, row in plate_indices.iterrows():
        code = row['code']  # 统一用code
        daily_data = reader.daily(symbol=code)
        if daily_data is not None and not daily_data.empty:
            all_dates_in_data.update(daily_data.index.date)
    if not all_dates_in_data:
        print("所有板块都没有数据")
        return pd.DataFrame()
    # 取交集
    trade_dates = sorted(set([pd.to_datetime(d).date() for d in all_trade_dates]) & all_dates_in_data)
    if len(trade_dates) < CONFIG['days']:
        print(f'实际可用交易日只有{len(trade_dates)}天')
    # 用实际有数据的最近N天
    use_dates = trade_dates[-CONFIG['days']:]
    use_dates_set = set(use_dates)
    results = []
    debug_rows = []
    for _, row in plate_indices.iterrows():
        code = row['code']  # 统一用code
        name = row['name']
        try:
            daily_data = reader.daily(symbol=code)
            if daily_data is None or daily_data.empty:
                continue
            # 保留volume字段
            if 'volume' not in daily_data.columns:
                if 'vol' in daily_data.columns:
                    daily_data['volume'] = daily_data['vol']
                else:
                    daily_data['volume'] = np.nan
            # 强制类型转换，防止全为NaN
            daily_data['open'] = pd.to_numeric(daily_data['open'], errors='coerce')
            daily_data['close'] = pd.to_numeric(daily_data['close'], errors='coerce')
            daily_data['high'] = pd.to_numeric(daily_data['high'], errors='coerce')
            daily_data['low'] = pd.to_numeric(daily_data['low'], errors='coerce')
            daily_data['volume'] = pd.to_numeric(daily_data['volume'], errors='coerce')
            daily_data['change'] = (daily_data['close'] - daily_data['open']) / daily_data['open'] * 100
            daily_data['pct_change'] = daily_data['close'].pct_change() * 100
            # print(f"[DEBUG] {code} change head: {daily_data['change'].head().to_list()}")
            # print(f"[DEBUG] {code} pct_change head: {daily_data['pct_change'].head().to_list()}")
            # print(f"[DEBUG] {code} change all NaN: {daily_data['change'].isna().all()}")
            # print(f"[DEBUG] {code} pct_change all NaN: {daily_data['pct_change'].isna().all()}")
            print(f"[DEBUG] daily_data.columns before adding code: {daily_data.columns}")
            daily_data['code'] = code
            daily_data['name'] = name
            daily_data['date'] = daily_data.index
            fields_to_keep = ['code', 'name', 'date', 'open', 'high', 'low', 'close', 'change', 'pct_change', 'volume']
            for col in fields_to_keep:
                if col not in daily_data.columns:
                    daily_data[col] = np.nan
            # print(f"[DEBUG] fields_to_keep: {fields_to_keep}")
            # print(f"[DEBUG] daily_data[fields_to_keep].head():\n{daily_data[fields_to_keep].head()}")
            tmp = daily_data[fields_to_keep].copy()
            tmp = tmp.reset_index(drop=True)
            results.append(tmp)
            debug_df = daily_data[fields_to_keep].copy()
            debug_rows.append(debug_df)
        except Exception as e:
            print(f"处理{code}({name})失败: {str(e)}")
            print(f"[DEBUG][EXCEPTION] daily_data.columns: {daily_data.columns if 'daily_data' in locals() else 'N/A'}")
            if 'daily_data' in locals():
                print(f"[DEBUG][EXCEPTION] daily_data.head():\n{daily_data.head()}")
    # 保存所有调试信息到csv
    if debug_rows:
        debug_all = pd.concat(debug_rows)
        debug_all.to_csv(os.path.join('tdx_rps_subjob', 'debug_plate_both_changes.csv'), index=False, encoding='utf-8-sig')
        print('已保存中间过程到 tdx_rps_subjob/debug_plate_both_changes.csv')
    if not results:
        print("[DEBUG] calculate_both_changes: results is empty!")
    else:
        print("[DEBUG] calculate_both_changes: columns:", results[0].columns)
    if not results:
        return pd.DataFrame()
    return pd.concat(results)

def get_top_10_daily_changes(all_changes, change_col='change'):
    """获取每日涨幅前10的板块指数"""
    all_changes = all_changes.reset_index()
    # groupby 用 'date' 字段，避免 date 列为 0,1,2
    top_10 = all_changes.groupby('date', group_keys=False).apply(
        lambda x: x.nlargest(10, change_col)[['date', 'code', 'name', change_col]]
    )
    formatted_results = []
    for date, group in top_10.groupby('date'):
        daily_result = {'date': date}
        for i, (_, row) in enumerate(group.iterrows(), 1):
            daily_result[f'rank{i}_code'] = row['code']
            daily_result[f'rank{i}_name'] = row['name']
            daily_result[f'rank{i}_change'] = round(row[change_col], 2) if not pd.isna(row[change_col]) else ''
        formatted_results.append(daily_result)
    return pd.DataFrame(formatted_results)

def save_to_csv(results_df, output_file):
    """保存结果到指定CSV文件，按日期降序（最近日期在最上面），除all_plate_rpsN外都放tdx_rps_subjob下"""
    # 如果是all_plate_rpsN.csv，保持原路径
    if output_file.startswith('all_plate_rps'):
        out_path = os.path.join('tdx_rps_subjob', output_file)
    else:
        out_path = os.path.join('tdx_rps_subjob', os.path.basename(output_file))
    if 'date' in results_df.columns:
        results_df = results_df.sort_values('date', ascending=False)
    output_dir = os.path.dirname(out_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    if os.path.exists(out_path):
        results_df.to_csv(
            out_path,
            mode='a',
            header=False,
            index=False,
            encoding='utf-8-sig'
        )
    else:
        results_df.to_csv(
            out_path,
            index=False,
            encoding='utf-8-sig'
        )
    print(f"结果已保存到 {out_path}")

def save_top_10_plates(all_changes):
    """保存每日涨幅前10名板块到csv（change和pct_change两种方式）"""
    top_10_results = get_top_10_daily_changes(all_changes, change_col='change')
    top_10_results_pct = get_top_10_daily_changes(all_changes, change_col='pct_change')
    if top_10_results.empty or top_10_results_pct.empty:
        print("未生成有效的排名数据")
        return
    save_to_csv(top_10_results, 'top_plate_indices_change.csv')  # 板块的实体涨幅
    save_to_csv(top_10_results_pct, 'top_plate_indices_pct_change.csv')  # 板块的真正百分比涨幅
    print("板块指数涨幅分析结果已保存")

def run_plate_analysis():
    """执行板块指数涨幅分析主流程，返回all_changes。"""
    # 初始化通达信读取器
    reader = Reader.factory(market='std', tdxdir=CONFIG['tdx_path'])
    print("通达信读取器初始化成功")
    
    # 获取板块指数列表
    plate_indices = get_plate_indices()
    if plate_indices.empty:
        print("未找到符合条件的板块指数")
        return
    
    # 计算每日涨幅
    all_changes = calculate_both_changes(reader, plate_indices)
    print("[DEBUG] all_changes in run_plate_analysis, type:", type(all_changes))
    if isinstance(all_changes, pd.DataFrame):
        print("[DEBUG] all_changes.columns in run_plate_analysis:", all_changes.columns)
        print("[DEBUG] all_changes.head() in run_plate_analysis:\n", all_changes.head())
    else:
        print("[DEBUG] all_changes is not a DataFrame:", all_changes)
    if all_changes.empty:
        print("未获取到有效的涨幅数据")
        return
    return all_changes

def calc_plate_rps(all_changes, target_date, output_dir='tdx_rps_subjob', save_path=None):
    import pandas as pd, os
    print('[DEBUG] === calc_plate_rps: 入口 ===')
    print('[DEBUG] all_changes.shape:', all_changes.shape)
    print('[DEBUG] all_changes.columns:', list(all_changes.columns))
    print('[DEBUG] all_changes[date] min:', all_changes['date'].min(), 'max:', all_changes['date'].max())
    print('[DEBUG] all_changes[date].value_counts().head(10):\n', all_changes['date'].value_counts().head(10))
    df = all_changes.copy()
    print(f"[DEBUG] all_changes.columns: {df.columns}")
    if 'code' not in df.columns and 'symbol' in df.columns:
        print("[DEBUG] Renaming symbol to code")
        df = df.rename(columns={'symbol': 'code'})
    print(f"[DEBUG] df.columns after rename: {df.columns}")
    print('[DEBUG] after copy, df.shape:', df.shape)
    print('[DEBUG] after copy, df[date] min:', df['date'].min(), 'max:', df['date'].max())
    print('[DEBUG] after copy, df[date].value_counts().head(10):\n', df['date'].value_counts().head(10))
    print(f"[DEBUG] Before code filter, df.columns: {df.columns}")
    df = df[df['code'].str[2:5] == '880']  # code如sh880568
    print(f"[DEBUG] After code filter, df.columns: {df.columns}")
    print('[DEBUG] after code filter, df[date].value_counts().head(10):\n', df['date'].value_counts().head(10))
    print(f"[DEBUG] Before name filter, df.columns: {df.columns}")
    df = df[df['name'] != df['code']]     # 有中文名
    print(f"[DEBUG] After name filter, df.columns: {df.columns}")
    print('[DEBUG] after name filter, df[date].value_counts().head(10):\n', df['date'].value_counts().head(10))
    # 避免重复列
    if 'symbol' not in df.columns and 'code' in df.columns:
        pass  # 已经只有code
    elif 'code' in df.columns and 'symbol' in df.columns:
        if df['code'].equals(df['symbol']):
            df = df.drop(columns=['symbol'])
        else:
            df = df.rename(columns={'symbol': 'code_symbol'})
    print('[DEBUG] after code/symbol处理, df.columns:', list(df.columns))
    print('[DEBUG] after code/symbol处理, df.shape:', df.shape)
    if 'close' not in df.columns:
        print('警告：数据缺少close列，无法计算RPS')
        return
    # 统一date类型
    df['date'] = pd.to_datetime(df['date'])
    date = pd.to_datetime(target_date)
    print('[DEBUG] after date类型统一, df[date] min:', df['date'].min(), 'max:', df['date'].max())
    print('[DEBUG] after date类型统一, df[date].value_counts().head(10):\n', df['date'].value_counts().head(10))
    # 检查是否有重复的code+date
    dup = df.duplicated(subset=['code', 'date'], keep=False)
    if dup.any():
        print("[DEBUG] 存在重复的 code+date 行：")
        print(df[dup])
    print(f"[DEBUG] Before sort, df.columns: {df.columns}")
    df = df.sort_values(['code', 'date']).reset_index(drop=True)
    print(f"[DEBUG] After sort, df.columns: {df.columns}")
    print('[DEBUG] after sort, df.shape:', df.shape)
    print('[DEBUG] after sort, df[date].min:', df['date'].min(), 'max:', df['date'].max())
    print('[DEBUG] after sort, df[date].value_counts().head(10):\n', df['date'].value_counts().head(10))
    # debug: 每个code全部日期和close
    for code in df['code'].unique()[:3]:
        code_df = df[df['code'] == code].sort_values('date')
        print(f'[DEBUG] {code} 全部日期和close：')
        print(code_df[['date', 'close']].tail(10))
    # 计算5日均量
    df['volume_5d_avg'] = df.groupby('code')['volume'].rolling(5).mean().reset_index(level=0, drop=True)
    for N in [5, 10, 20, 60]:
        df = df.sort_values(['code', 'date']).reset_index(drop=True)
        df[f'close_N_days_ago'] = df.groupby('code')['close'].shift(N-1)
        # debug: shift后目标日和前N天的close
        for code in df['code'].unique()[:3]:
            code_df = df[df['code'] == code].sort_values('date')
            print(f'[DEBUG] {code} {N}日shift后：')
            print(code_df[['date', 'close', f'close_N_days_ago']].tail(N+1))
        df[f'change_{N}'] = (df['close'] / df[f'close_N_days_ago'] - 1) * 100
        print(f'[DEBUG] {N}日RPS，目标日change_{N}统计：')
        print(df[df['date'] == date][['code', 'close', f'close_N_days_ago', f'change_{N}']].head(10))
        df[f'rps{N}_rank'] = df.groupby('date')[f'change_{N}'].rank(method='min', ascending=False)
        total = df.groupby('date')[f'change_{N}'].transform('count')
        df[f'rps{N}'] = ((total - df[f'rps{N}_rank']) / (total - 1) * 100).round(2)
    # 只保留目标日期
    print('[DEBUG] df.columns:', list(df.columns))
    print(f'[DEBUG] 目标日期{date}的df内容:')
    print(df[df['date'] == date].head())
    # 允许保存更多原始行情字段
    base_cols = ['code', 'name', 'date']
    extra_cols = []
    for col in ['open', 'close', 'high', 'low', 'change', 'pct_change', 'volume']:
        if col in df.columns:
            extra_cols.append(col)
    rps_cols = ['change_5', 'change_10', 'change_20', 'change_60', 'rps5', 'rps10', 'rps20', 'rps60', 'volume_5d_avg']
    save_cols = base_cols + extra_cols + rps_cols
    # 去重，防止列重复
    save_cols = [c for i, c in enumerate(save_cols) if c not in save_cols[:i]]
    snapshot = df[df['date'] == date][save_cols]
    snapshot = snapshot.sort_values('change_5', ascending=False)
    # 保存到指定目录
    if save_path is not None:
        out_path = save_path
    else:
        out_path = os.path.join('tdx_rps_subjob/bankuai_rps_date', f'plate_rps_{date.strftime("%Y%m%d")}.csv')
    snapshot.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f'多周期概念板块涨幅和RPS已保存到 {out_path}')
    return snapshot

def check_plate_buy_point1(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
    """
    买点筛选条件：
    - rps60 < 60;
    - rps5 > 60 && rps5 - pre_rps5 > 15 && rps10 - pre_rps10 > 20 && rps20 - pre_rps20 > 10
    - volume > pre_volume * 1.3
    """
    try:
        rps5 = float(rps5)
        pre_rps5 = float(pre_rps5) if pre_rps5 is not None else None
        rps10 = float(rps10)
        pre_rps10 = float(pre_rps10) if pre_rps10 is not None else None
        rps20 = float(rps20)
        pre_rps20 = float(pre_rps20) if pre_rps20 is not None else None
        rps60 = float(rps60)
        pre_rps60 = float(pre_rps60) if pre_rps60 is not None else None
        volume = float(volume) if volume is not None else None
        pre_volume = float(pre_volume) if pre_volume is not None else None
        volume_5d_avg = float(volume_5d_avg) if volume_5d_avg is not None else None
    except Exception:
        return False
    return (
        rps60 < 60
        and rps5 > 60 and (pre_rps5 is not None and rps5 - pre_rps5 > 15)
        and (pre_rps10 is not None and rps10 - pre_rps10 > 20)
        and (pre_rps20 is not None and rps20 - pre_rps20 > 10)
        and (pre_volume is not None and volume is not None and volume > pre_volume * 1.3)
    )

def check_plate_buy_point2(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
    """
    买点筛选条件：
    - rps5 > 80
    - pre_rps5 < 70
    - rps5 - pre_rps5 > 20
    - rps10 > 80
    - rps20 > 80
    - rps60 > 50
    - volume > pre_volume * 1.5
    """
    try:
        rps5 = float(rps5)
        pre_rps5 = float(pre_rps5) if pre_rps5 is not None else None
        rps10 = float(rps10)
        rps20 = float(rps20)
        rps60 = float(rps60)
        volume = float(volume) if volume is not None else None
        pre_volume = float(pre_volume) if pre_volume is not None else None
    except Exception:
        return False
    return (
        rps5 > 80
        and (pre_rps5 is not None and pre_rps5 < 70)
        and (pre_rps5 is not None and rps5 - pre_rps5 > 20)
        and rps10 > 80
        and rps20 > 80
        and rps60 > 50
        and (pre_volume is not None and volume is not None and volume > pre_volume * 1.5)
    )

def check_plate_buy_point3(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
    """
    买点筛选条件：
    - rps5 - pre_rps5 > 40
    - rps10 - pre_rps10 > 40
    - rps20 - pre_rps20 > 20
    - rps60 > 80
    - volume > pre_volume * 1.1
    """
    try:
        rps5 = float(rps5)
        pre_rps5 = float(pre_rps5) if pre_rps5 is not None else None
        rps10 = float(rps10)
        rps20 = float(rps20)
        rps60 = float(rps60)
        volume = float(volume) if volume is not None else None
        pre_volume = float(pre_volume) if pre_volume is not None else None
    except Exception:
        return False
    return (
        (pre_rps5 is not None and rps5 - pre_rps5 > 40)
        and (pre_rps10 is not None and rps10 - pre_rps10 > 40)
        and (pre_rps20 is not None and rps20 - pre_rps20 > 20)
        and rps60 > 80
        and (pre_volume is not None and volume is not None and volume > pre_volume * 1.1)
    )



def find_plate_buy_points(snapshot_dir='tdx_rps_subjob/bankuai_rps_date'):
    """
    遍历所有快照文件，找出板块rps5从低位突破80且rps20>rps60的买点，输出日期和板块名称。
    新增：二次筛选，要求当天涨幅>2%，且量能>5日均量1.2倍。
    """
    # 收集所有快照文件，按日期排序
    files = [f for f in os.listdir(snapshot_dir) if f.startswith('plate_rps_') and f.endswith('.csv')]
    files = sorted(files)
    # 记录每个板块的rps5序列
    plate_rps_history = {}
    plate_name_map = {}
    date_list = []
    for fname in files:
        date_str = fname.replace('plate_rps_', '').replace('.csv', '')
        date_list.append(date_str)
        df = pd.read_csv(os.path.join(snapshot_dir, fname), dtype={'code': str})
        # 兼容老快照无volume/volume_5d_avg
        for _, row in df.iterrows():
            code = row['code']
            name = row['name']
            rps5 = row['rps5']
            rps10 = row['rps10']
            rps20 = row['rps20']
            rps60 = row['rps60']
            change_5 = row['change_5'] if 'change_5' in row else None
            volume = row['volume'] if 'volume' in row else None
            volume_5d_avg = row['volume_5d_avg'] if 'volume_5d_avg' in row else None
            if code not in plate_rps_history:
                plate_rps_history[code] = []
                plate_name_map[code] = name
            plate_rps_history[code].append({'date': date_str, 'rps5': rps5, 'rps10': rps10, 'rps20': rps20, 'rps60': rps60, 'change_5': change_5, 'volume': volume, 'volume_5d_avg': volume_5d_avg})
    # 新增：先保存所有明细到csv
    all_history_rows = []
    for fname in files:
        date_str = fname.replace('plate_rps_', '').replace('.csv', '')
        df = pd.read_csv(os.path.join(snapshot_dir, fname), dtype={'code': str})
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            row_dict['date'] = date_str  # 确保date字段一致
            all_history_rows.append(row_dict)
    all_history_df = pd.DataFrame(all_history_rows)
    all_history_df = all_history_df.sort_values(['date', 'code'])

    # 获取标准字段顺序
    if files:
        latest_file = os.path.join(snapshot_dir, files[-1])
        standard_cols = list(pd.read_csv(latest_file, nrows=1).columns)
        for col in standard_cols:
            if col not in all_history_df.columns:
                all_history_df[col] = None
        all_history_df = all_history_df[standard_cols]
    # 统一date为datetime类型
    all_history_df['date'] = pd.to_datetime(all_history_df['date'])
    all_history_df.to_csv('tdx_rps_subjob/plate_rps_history.csv', index=False, encoding='utf-8-sig')
    print('所有板块RPS历史明细已保存到 tdx_rps_subjob/plate_rps_history.csv')
    
    
    
    # 买点筛选
    print('日期,板块名称,板块代码')
    results1 = []
    results2 = []
    results3 = []
    for code, rps_list in plate_rps_history.items():
        pre_rps5 = pre_rps10 = pre_rps20 = pre_rps60 = pre_volume = None
        for i, item in enumerate(rps_list):
            rps5 = item['rps5']
            rps10 = item['rps10']
            rps20 = item['rps20']
            rps60 = item['rps60']
            volume = item.get('volume', None)
            volume_5d_avg = item.get('volume_5d_avg', None)
            if check_plate_buy_point1(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
                results1.append((item['date'], plate_name_map[code], code))
            if check_plate_buy_point2(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
                results2.append((item['date'], plate_name_map[code], code))
            if check_plate_buy_point3(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
                results3.append((item['date'], plate_name_map[code], code))
            pre_rps5 = rps5
            pre_rps10 = rps10
            pre_rps20 = rps20
            pre_rps60 = rps60
            pre_volume = volume
    # 按日期排序并输出
    print(f"激进买点：")
    results1.sort(key=lambda x: x[0])
    for row in results1:
        print(f"{row[0]},{row[1]},{row[2]}")

    print(f"确定买点：")
    results2.sort(key=lambda x: x[0])
    for row in results2:
        print(f"{row[0]},{row[1]},{row[2]}")
    
    print(f"浅回调买点：")
    results3.sort(key=lambda x: x[0])
    for row in results3:
        print(f"{row[0]},{row[1]},{row[2]}")


def get_real_time_plate_data():
    """
    实时获取所有板块指数的行情数据
    返回包含代码、名称、最新价、成交量等信息的DataFrame
    """
    # 获取板块指数列表
    plate_indices = get_plate_indices()
    if plate_indices.empty:
        print("未找到符合条件的板块指数")
        return pd.DataFrame()
    
    # 初始化实时行情API
    quotes = Quotes.factory(market='std', 
                           tdxdir=CONFIG['tdx_path'],
                           server=CONFIG['real_time_server'],
                           port=CONFIG['real_time_port'])
    
    real_time_data = []
    
    # 分批获取实时行情（每次最多80只）
    batch_size = 80
    codes = plate_indices['code'].tolist()  # 这里codes是sh880xxx/sz880xxx
    for i in range(0, len(codes), batch_size):
        batch_codes = codes[i:i + batch_size]
        batch_codes_set = set(batch_codes)
        try:
            batch_quotes = quotes.quotes(symbol=batch_codes)
            if batch_quotes is None or len(batch_quotes) == 0:
                print(f"警告: 实时行情接口未返回数据, symbols={batch_codes}")
                continue
            for idx, row in batch_quotes.iterrows():
                # row['code'] 是880xxx，batch_codes里是sh880xxx
                # 找到对应symbol
                code_no_prefix = str(row['code'])
                symbol = None
                for s in batch_codes:
                    if s.endswith(code_no_prefix):
                        symbol = s
                        break
                if symbol is None:
                    print(f'警告: 返回的code={row["code"]}找不到对应symbol，已跳过')
                    continue
                name_row = plate_indices.loc[plate_indices['code'] == symbol, 'name']
                if not name_row.empty:
                    name = name_row.values[0]
                else:
                    print(f'警告: symbol={symbol}在板块列表中找不到，已跳过')
                    continue
                real_time_data.append({
                    'code': symbol,
                    'symbol': symbol,  # 新增，兼容后续分析
                    'name': name,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'close': row['price'],
                    'volume': row['volume']
                })
        except Exception as e:
            print(f"获取实时行情失败: {str(e)}")
    
    return pd.DataFrame(real_time_data)

def update_plate_daily_data(real_time_df):
    """
    合并历史数据和本次实时数据，去重后保存。
    """
    daily_data_path = os.path.join('tdx_rps_subjob', 'plate_daily_data.csv')
    if os.path.exists(daily_data_path):
        old_data = pd.read_csv(daily_data_path, dtype={'code': str})
        old_data['date'] = pd.to_datetime(old_data['date'])
        # 合并并去重（以code+date为唯一键）
        updated_data = pd.concat([old_data, real_time_df], ignore_index=True)
        updated_data = updated_data.drop_duplicates(subset=['code', 'date'], keep='last')
    else:
        updated_data = real_time_df.copy()
    print("[DEBUG] update_plate_daily_data: about to save updated_data")
    print("[DEBUG] updated_data.columns:", list(updated_data.columns))
    print("[DEBUG] updated_data.shape:", updated_data.shape)
    print("[DEBUG] updated_data.head():\n", updated_data.head())
    if 'symbol' not in updated_data.columns and 'code' in updated_data.columns:
        updated_data['symbol'] = updated_data['code']
    updated_data['date'] = pd.to_datetime(updated_data['date'])
    updated_data.to_csv(daily_data_path, index=False, encoding='utf-8-sig')
    print(f"板块日线数据已更新到 {daily_data_path}")
    return updated_data

def real_time_plate_rps():
    import pandas as pd, os, numpy as np
    from datetime import datetime

    # 1. 读取历史RPS明细
    history_path = os.path.join('tdx_rps_subjob', 'plate_rps_history.csv')
    if os.path.exists(history_path):
        history_df = pd.read_csv(history_path, dtype={'code': str})
        history_df['date'] = pd.to_datetime(history_df['date'])
    else:
        history_df = pd.DataFrame()

    # 2. 获取实时数据
    real_time_df = get_real_time_plate_data()
    print("[DEBUG] real_time_df.columns:", list(real_time_df.columns))
    print("[DEBUG] real_time_df.shape:", real_time_df.shape)
    print("[DEBUG] real_time_df.head():\n", real_time_df.head())
    if real_time_df.empty:
        print("未获取到实时行情数据")
        return pd.DataFrame()

    # 3. 只保留历史的昨天及以前
    today = datetime.now().strftime('%Y-%m-%d')
    today_date = pd.to_datetime(today)
    history_df['date'] = pd.to_datetime(history_df['date'])
    real_time_df['date'] = pd.to_datetime(real_time_df['date'])
    history_df = history_df[history_df['date'] < today_date]
    print("[DEBUG] history_df.tail():\n", history_df.tail(10))
    print("[DEBUG] history_df[date==昨天]:\n", history_df[history_df['date'] == (today_date - pd.Timedelta(days=1))])

    # 4. 用今天的实时行情补充/覆盖历史
    keep_cols = ['code', 'name', 'date', 'close', 'volume']
    for col in keep_cols:
        if col not in real_time_df.columns:
            real_time_df[col] = np.nan
    for col in history_df.columns:
        if col not in real_time_df.columns:
            real_time_df[col] = np.nan
    for col in real_time_df.columns:
        if col not in history_df.columns:
            history_df[col] = np.nan

    print("[DEBUG] real_time_df for today:", real_time_df.head(10))

    # 合并历史所有天和今天的实时数据，保留所有历史天和今天
    all_data = pd.concat([history_df, real_time_df], ignore_index=True)
    all_data = all_data.drop_duplicates(subset=['code', 'date'], keep='last')
    all_data = all_data.sort_values(['code', 'date']).reset_index(drop=True)
    print("[DEBUG] all_data[date==today]:\n", all_data[all_data['date'] == today_date].head(10))
    # 检查目标日期前5天的内容
    for code in all_data['code'].unique()[:5]:
        code_df = all_data[all_data['code'] == code].sort_values('date')
        print(f"[DEBUG] {code} 最近6天: {code_df[['date','close']].tail(6).to_string(index=False)}")

    # 5. 计算RPS
    date_str = datetime.now().strftime("%Y%m%d")
    save_path = os.path.join('tdx_rps_subjob', f'realtime_plate_rps_{date_str}.csv')
    rps_df = calc_plate_rps(all_data, today, save_path=save_path)
    if rps_df is not None and not rps_df.empty:
        print(f"实时板块RPS已保存到 {save_path}")
    
    # 6. 自动调用买点扫描逻辑，输出最新买点
    print("===== 实时买点扫描结果 =====")
    find_today_plate_buy_points()
    print("===== 实时买点扫描结束 =====")
    return rps_df

def find_today_plate_buy_points():
    """
    只读取昨天的快照（plate_rps_YYYYMMDD.csv）和今天的plate_rps_history.csv，判断今天的买点。
    """
    import pandas as pd, os
    from datetime import datetime, timedelta
    # 获取今天和昨天日期
    today = datetime.now().date()
    yesterday = get_previous_trade_date(today)
    # 找到昨天的快照文件
    snapshot_dir = 'tdx_rps_subjob/bankuai_rps_date'
    # 昨日快照
    yesterday_file = os.path.join(snapshot_dir, f'plate_rps_{yesterday.strftime("%Y%m%d")}.csv')
    # 今日实时RPS
    today_file = os.path.join('tdx_rps_subjob', f'realtime_plate_rps_{today.strftime("%Y%m%d")}.csv')
    if not os.path.exists(yesterday_file):
        print(f"未找到昨日快照文件: {yesterday_file}")
        return
    if not os.path.exists(today_file):
        print(f"未找到今日实时RPS文件: {today_file}")
        return
    df_yesterday = pd.read_csv(yesterday_file, dtype={'code': str})
    df_today = pd.read_csv(today_file, dtype={'code': str})
    # 取今天最新日期
    df_today['date'] = pd.to_datetime(df_today['date'])
    today_str = df_today['date'].max().strftime('%Y-%m-%d')
    df_today = df_today[df_today['date'] == df_today['date'].max()]
    # 建立昨天的rps/volume映射
    pre_map = {}
    for _, row in df_yesterday.iterrows():
        pre_map[row['code']] = {
            'rps5': row['rps5'] if 'rps5' in row else None,
            'rps10': row['rps10'] if 'rps10' in row else None,
            'rps20': row['rps20'] if 'rps20' in row else None,
            'rps60': row['rps60'] if 'rps60' in row else None,
            'volume': row['volume'] if 'volume' in row else None,
        }
    # 买点筛选
    print('日期,板块名称,板块代码')
    results1 = []
    results2 = []
    results3 = []
    for _, row in df_today.iterrows():
        code = row['code']
        name = row['name']
        rps5 = row['rps5'] if 'rps5' in row else None
        rps10 = row['rps10'] if 'rps10' in row else None
        rps20 = row['rps20'] if 'rps20' in row else None
        rps60 = row['rps60'] if 'rps60' in row else None
        volume = row['volume'] if 'volume' in row else None
        volume_5d_avg = row['volume_5d_avg'] if 'volume_5d_avg' in row else None
        pre = pre_map.get(code, {})
        pre_rps5 = pre.get('rps5', None)
        pre_rps10 = pre.get('rps10', None)
        pre_rps20 = pre.get('rps20', None)
        pre_rps60 = pre.get('rps60', None)
        pre_volume = pre.get('volume', None)
        if check_plate_buy_point1(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
            results1.append((today_str, name, code))
        if check_plate_buy_point2(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
            results2.append((today_str, name, code))
        if check_plate_buy_point3(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
            results3.append((today_str, name, code))
    print(f"激进买点：")
    for row in results1:
        print(f"{row[0]},{row[1]},{row[2]}")
    print(f"确定买点：")
    for row in results2:
        print(f"{row[0]},{row[1]},{row[2]}")
    print(f"浅回调买点：")
    for row in results3:
        print(f"{row[0]},{row[1]},{row[2]}")


def main():
    """主程序"""
    import sys
    try:
        # 检查是否实时模式
        if '--real-time' in sys.argv:
            print("===== 实时板块RPS计算模式 =====")
            real_time_plate_rps()
            print("实时计算完成")
            return

        # 原有主流程
        print("===== 常规板块分析模式 =====")
        all_changes = run_plate_analysis()
        if all_changes is not None:
            print("[DEBUG] all_changes.columns after run_plate_analysis:", all_changes.columns)
            print("[DEBUG] all_changes.head():\n", all_changes.head())
            save_top_10_plates(all_changes)
            # 获取今天之前的61个交易日
            today = datetime.now().date()
            trade_dates = []
            cur_date = today
            if is_trade_date(today):
                trade_dates.append(today)
            for _ in range(CONFIG['days']):
                cur_date = get_previous_trade_date(cur_date)
                trade_dates.append(cur_date)
            trade_dates = sorted(set(trade_dates))
            for d in trade_dates:
                out_path = os.path.join('tdx_rps_subjob/bankuai_rps_date', f'plate_rps_{d.strftime("%Y%m%d")}.csv')
                if os.path.exists(out_path):
                    print(f"{out_path} 已存在，跳过计算")
                    continue
                calc_plate_rps(all_changes, d.strftime('%Y-%m-%d'))
            # 可在main()中调用 find_plate_buy_points() 进行买点扫描
            find_plate_buy_points()
        print("程序执行完成")
    except Exception as e:
        import traceback
        print(f"程序执行出错: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"程序执行出错: {str(e)}")
        traceback.print_exc()