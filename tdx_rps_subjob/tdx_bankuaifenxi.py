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
import glob
from core.trade_time import stock_trade_date, get_previous_trade_date, is_trade_date  # 新增导入
import sys

# 配置参数
CONFIG = {
    'tdx_path': '/mnt/c/new_tdx',  # 通达信安装路径
    'output_file': 'top_plate_indices.csv',  # 输出文件名
    'plate_prefixes': ['880', '885', '886', '887', '399'],  # 板块指数前缀
    'days': 121  # 分析天数（最近一年）
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
        symbol = row['code']
        daily_data = reader.daily(symbol=symbol)
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
        symbol = row['code']
        name = row['name']
        try:
            daily_data = reader.daily(symbol=symbol)
            # print(f"{symbol} 日线数据: {None if daily_data is None else len(daily_data)} 行")
            if daily_data is None or daily_data.empty:
                continue
            mask = pd.Series(daily_data.index.date, index=daily_data.index).isin(use_dates_set)
            daily_data = daily_data.loc[mask]
            # print(f"{symbol} 过滤后剩余: {len(daily_data)} 行, 日期: {list(daily_data.index.date)}")
            if len(daily_data) < 2:
                continue
            daily_data['change'] = (daily_data['close'] - daily_data['open']) / daily_data['open'] * 100
            daily_data['pct_change'] = daily_data['close'].pct_change() * 100
            daily_data['symbol'] = symbol
            daily_data['name'] = name
            # 不再强制 daily_data['date'] = daily_data.index
            debug_df = daily_data[['symbol', 'name', 'open', 'close', 'change', 'pct_change']].copy()
            debug_df['date'] = daily_data.index
            debug_rows.append(debug_df)
            # 结果输出时，date直接用index或已有date列，且都reset_index(drop=True)
            if 'date' in daily_data.columns:
                tmp = daily_data[['symbol', 'name', 'date', 'close', 'change', 'pct_change']].copy()
                tmp = tmp.reset_index(drop=True)
                results.append(tmp)
            else:
                tmp = daily_data[['symbol', 'name', 'close', 'change', 'pct_change']].copy()
                tmp['date'] = daily_data.index
                tmp = tmp.reset_index(drop=True)
                results.append(tmp)
        except Exception as e:
            print(f"处理{symbol}({name})失败: {str(e)}")
    # 保存所有调试信息到csv
    if debug_rows:
        debug_all = pd.concat(debug_rows)
        debug_all.to_csv(os.path.join('tdx_rps_subjob', 'debug_plate_both_changes.csv'), index=False, encoding='utf-8-sig')
        print('已保存中间过程到 tdx_rps_subjob/debug_plate_both_changes.csv')
    if not results:
        return pd.DataFrame()
    return pd.concat(results)

def get_top_10_daily_changes(all_changes, change_col='change'):
    """获取每日涨幅前10的板块指数"""
    all_changes = all_changes.reset_index()
    # groupby 用 'date' 字段，避免 date 列为 0,1,2
    top_10 = all_changes.groupby('date', group_keys=False).apply(
        lambda x: x.nlargest(10, change_col)[['date', 'symbol', 'name', change_col]]
    )
    formatted_results = []
    for date, group in top_10.groupby('date'):
        daily_result = {'date': date}
        for i, (_, row) in enumerate(group.iterrows(), 1):
            daily_result[f'rank{i}_code'] = row['symbol']
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
    if all_changes.empty:
        print("未获取到有效的涨幅数据")
        return
    return all_changes

def calc_plate_rps(all_changes, target_date, output_dir='tdx_rps_subjob'):
    """按指定日期输出快照csv，文件名带日期。"""
    import pandas as pd, os
    df = all_changes.copy()
    df = df[df['symbol'].str[2:5] == '880']  # symbol如sh880568
    df = df[df['name'] != df['symbol']]     # 有中文名
    df = df.rename(columns={'symbol': 'code'})
    if 'close' not in df.columns:
        print('警告：数据缺少close列，无法计算RPS')
        return
    for N in [5, 10, 20, 60]:
        df = df.sort_values(['code', 'date'])
        df[f'close_N_days_ago'] = df.groupby('code')['close'].shift(N-1)
        df[f'change_{N}'] = (df['close'] / df[f'close_N_days_ago'] - 1) * 100
        df[f'rps{N}_rank'] = df.groupby('date')[f'change_{N}'].rank(method='min', ascending=False)
        total = df.groupby('date')[f'change_{N}'].transform('count')
        df[f'rps{N}'] = ((total - df[f'rps{N}_rank']) / (total - 1) * 100).round(2)
    # 只保留目标日期
    date = pd.to_datetime(target_date)
    snapshot = df[df['date'] == date][['code', 'name', 'change_5', 'change_10', 'change_20', 'change_60', 'rps5', 'rps10', 'rps20', 'rps60']]
    snapshot = snapshot.sort_values('change_5', ascending=False)
    # 保存到 bankuai_rps_date 目录
    out_path = os.path.join('tdx_rps_subjob/bankuai_rps_date', f'plate_rps_{date.strftime("%Y%m%d")}.csv')
    snapshot.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f'多周期概念板块涨幅和RPS已保存到 {out_path}')

def main():
    """主程序"""
    import sys
    try:
        # 运行主流程，获取结果
        all_changes = run_plate_analysis()
        if all_changes is not None:
            save_top_10_plates(all_changes)
            # 获取今天之前的61个交易日
            today = datetime.now().date()
            trade_dates = []
            cur_date = today
            for _ in range(CONFIG['days']):
                # 找到上一个交易日
                cur_date = get_previous_trade_date(cur_date)
                trade_dates.append(cur_date)
            trade_dates = sorted(trade_dates)
            for d in trade_dates:
                out_path = os.path.join('tdx_rps_subjob/bankuai_rps_date', f'plate_rps_{d.strftime("%Y%m%d")}.csv')
                if os.path.exists(out_path):
                    print(f"{out_path} 已存在，跳过计算")
                    continue
                calc_plate_rps(all_changes, d.strftime('%Y-%m-%d'))
        print("程序执行完成")
    except Exception as e:
        print(f"程序执行出错: {str(e)}")

if __name__ == "__main__":
    main()