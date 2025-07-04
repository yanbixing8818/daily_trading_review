import pandas as pd
import numpy as np
from mootdx.reader import Reader
from datetime import datetime, timedelta
import os
import glob

# 配置参数
CONFIG = {
    'tdx_path': '/mnt/c/new_tdx',  # 通达信安装路径
    'output_file': 'top_plate_indices.csv',  # 输出文件名
    'plate_prefixes': ['880', '885', '886', '887', '399'],  # 板块指数前缀
    'days': 2  # 分析天数（最近一年）
}

def load_plate_name_mapping(bankuai_dir='tdx_bankuai'):
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
    name_mapping = load_plate_name_mapping('tdx_bankuai')
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
                        # 名称优先用映射表，否则用代码
                        name = name_mapping.get(code)
                        if not name:
                            code_no_prefix = code[2:] if code.startswith(('sh', 'sz')) else code
                            name = name_mapping.get(code_no_prefix, code)
                        print(f"板块代码: {code}, 匹配到名称: {name}")
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
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=CONFIG['days'])
    results = []
    debug_rows = []
    for _, row in plate_indices.iterrows():
        symbol = row['code']
        name = row['name']
        try:
            daily_data = reader.daily(symbol=symbol)
            if daily_data is None or daily_data.empty:
                continue
            daily_data = daily_data[
                (daily_data.index >= start_date) & 
                (daily_data.index <= end_date)
            ]
            if len(daily_data) < 2:
                continue
            daily_data['change'] = (daily_data['close'] - daily_data['open']) / daily_data['open'] * 100
            daily_data['pct_change'] = daily_data['close'].pct_change() * 100
            daily_data['symbol'] = symbol
            daily_data['name'] = name
            debug_df = daily_data[['symbol', 'name', 'open', 'close', 'change', 'pct_change']].copy()
            debug_df['date'] = daily_data.index
            debug_rows.append(debug_df)
            results.append(daily_data[['symbol', 'name', 'change', 'pct_change']])
        except Exception as e:
            print(f"处理{symbol}({name})失败: {str(e)}")
    # 保存所有调试信息到csv
    if debug_rows:
        debug_all = pd.concat(debug_rows)
        debug_all.to_csv('debug_plate_both_changes.csv', index=False, encoding='utf-8-sig')
        print('已保存中间过程到 debug_plate_both_changes.csv')
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

def save_to_csv(results_df):
    """保存结果到CSV文件"""
    # 只在有目录时创建
    output_dir = os.path.dirname(CONFIG['output_file'])
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    # 保存到CSV
    if os.path.exists(CONFIG['output_file']):
        # 追加模式，不写入列名
        results_df.to_csv(
            CONFIG['output_file'], 
            mode='a', 
            header=False, 
            index=False,
            encoding='utf-8-sig'
        )
    else:
        # 新文件，写入列名
        results_df.to_csv(
            CONFIG['output_file'], 
            index=False,
            encoding='utf-8-sig'
        )
    print(f"结果已保存到 {CONFIG['output_file']}")

def main():
    """主程序"""
    try:
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
        
        # 获取每日前10名
        top_10_results = get_top_10_daily_changes(all_changes, change_col='change')
        top_10_results_pct = get_top_10_daily_changes(all_changes, change_col='pct_change')
        if top_10_results.empty or top_10_results_pct.empty:
            print("未生成有效的排名数据")
            return
        
        # 保存结果
        save_to_csv(top_10_results)
        save_to_csv(top_10_results_pct)
        
        print("程序执行完成")
    
    except Exception as e:
        print(f"程序执行出错: {str(e)}")

if __name__ == "__main__":
    main()