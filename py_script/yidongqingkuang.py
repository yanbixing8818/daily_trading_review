import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import akshare as ak
import time
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib
import plotly.io as pio
import re

def get_main_board_symbols():
    stock_df = ak.stock_info_a_code_name()
    main_board = stock_df[stock_df['code'].str.match(r'^(600|601|603|605|000|001)')].copy()
    def to_yf_code(row):
        code = row['code']
        if code.startswith(('600', '601', '603', '605')):
            return f"{code}.SS"
        else:
            return f"{code}.SZ"
    main_board['yf_code'] = main_board.apply(to_yf_code, axis=1)
    return main_board[['code', 'name', 'yf_code']]

def get_chuangye_board_symbols():
    stock_df = ak.stock_info_a_code_name()
    chuangye_board = stock_df[stock_df['code'].str.match(r'^300')].copy()
    chuangye_board['yf_code'] = chuangye_board['code'] + '.SZ'
    return chuangye_board[['code', 'name', 'yf_code']]

def get_kechuang_board_symbols():
    stock_df = ak.stock_info_a_code_name()
    kechuang_board = stock_df[stock_df['code'].str.match(r'^688')].copy()
    kechuang_board['yf_code'] = kechuang_board['code'] + '.SS'
    return kechuang_board[['code', 'name', 'yf_code']]

def get_beijiao_board_symbols():
    stock_df = ak.stock_info_a_code_name()
    beijiao_board = stock_df[stock_df['code'].str.match(r'^8')].copy()
    beijiao_board['yf_code'] = beijiao_board['code'] + '.BJ'
    return beijiao_board[['code', 'name', 'yf_code']]

def get_last_n_trading_days_with_today(symbol, n=10):
    end = datetime.now()
    start = end - timedelta(days=n*2)
    df = yf.download(symbol, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), auto_adjust=True)
    df = df.tail(n)
    ticker = yf.Ticker(symbol)
    try:
        last_price = ticker.fast_info['last_price']
        last_date = datetime.now().strftime('%Y-%m-%d')
        if len(df) == 0 or df.index[-1].strftime('%Y-%m-%d') != last_date:
            new_row = pd.Series({col: None for col in df.columns}, name=pd.Timestamp(last_date))
            new_row['Close'] = last_price
            df = pd.concat([df, new_row.to_frame().T])
    except Exception as e:
        print(f'获取今日最新价失败: {e}')
    return df

def calc_n_day_return_with_today(symbol, n=10):
    df = get_last_n_trading_days_with_today(symbol, n)
    if len(df) < n+1:
        print(f"数据不足{n+1}个交易日（含今天）")
        return None
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    try:
        start_price = float(close.iloc[0])
        end_price = float(close.iloc[-1])
        pct_change = (end_price - start_price) / start_price * 100
        print(f"{symbol} 近{n}个交易日+今日涨幅: {pct_change:.2f}%")
        return pct_change
    except Exception:
        return None

# ===================== 工具函数区 =====================
def filter_and_save(input_file, threshold, output_file, board_name):
    try:
        df = pd.read_excel(input_file)
        filtered = df[df['10日涨幅(含今日)%'] >= threshold]
        print(f'{board_name}10日涨幅大于等于{threshold}%的股票:')
        print(filtered)
        filtered.to_excel(output_file, index=False)
        print(f'已输出到 {output_file}')
    except Exception as e:
        print(f'筛选{board_name}时出错: {e}')

def insert_filtered_data(file_path, threshold, table_data, start_date, today):
    try:
        df = pd.read_excel(file_path)
        if not df.empty:
            for _, row in df.iterrows():
                actual_increase = round(row['10日涨幅(含今日)%'], 2)
                if actual_increase > 100:
                    remark = f"10日涨幅大于100%，为{actual_increase}%，已异动"
                else:
                    remaining_increase = round(100 - actual_increase, 2)
                    remark = f"明日涨幅{remaining_increase}%将异动"
                table_data.append([
                    str(row['股票代码']),
                    str(row['股票简称']),
                    start_date.strftime('%Y-%m-%d'),
                    today.strftime('%Y-%m-%d'),
                    remark
                ])
        else:
            table_data.append(["/", "/", "/", "/", "/"])
    except Exception as e:
        print(f"读取{file_path}失败: {e}")
        table_data.append(["/", "/", "/", "/", "/"])

def get_yidong_stocks(file_path, start_date, today):
    yidong = []
    try:
        df = pd.read_excel(file_path)
        if not df.empty:
            for _, row in df.iterrows():
                actual_increase = round(row['10日涨幅(含今日)%'], 2)
                if actual_increase > 100:
                    yidong.append([
                        str(row['股票代码']),
                        str(row['股票简称']),
                        start_date.strftime('%Y-%m-%d'),
                        today.strftime('%Y-%m-%d'),
                        f"10日涨幅大于100%，为{actual_increase}%，已异动"
                    ])
    except Exception as e:
        print(f"读取{file_path}失败: {e}")
    return yidong


if __name__ == "__main__":
    def process_board(board_name, get_board_symbols_func):
        board = get_board_symbols_func()
        results_10_days = []
        results_30_days = []
        
        for idx, row in board.iterrows():
            code, name, yf_code = row['code'], row['name'], row['yf_code']
            pct_10 = calc_n_day_return_with_today(yf_code, 10)
            pct_30 = calc_n_day_return_with_today(yf_code, 30)
            
            if pct_10 is not None:
                results_10_days.append({'股票代码': code, '股票简称': name, 'yfinance代码': yf_code, '10日涨幅(含今日)%': pct_10})
            if pct_30 is not None:
                results_30_days.append({'股票代码': code, '股票简称': name, 'yfinance代码': yf_code, '30日涨幅(含今日)%': pct_30})
            
            print(f"{code} {name} 10日涨幅: {pct_10 if pct_10 is not None else '无数据'}, 30日涨幅: {pct_30 if pct_30 is not None else '无数据'}")
            time.sleep(0.5)

        df_result_10_days = pd.DataFrame(results_10_days)
        df_result_10_days = df_result_10_days.sort_values('10日涨幅(含今日)%', ascending=False)
        df_result_10_days.to_excel(f'{board_name}10日涨幅排序.xlsx', index=False)
        print(f'已输出到 {board_name}10日涨幅排序.xlsx')

        df_result_30_days = pd.DataFrame(results_30_days)
        df_result_30_days = df_result_30_days.sort_values('30日涨幅(含今日)%', ascending=False)
        df_result_30_days.to_excel(f'{board_name}30日涨幅排序.xlsx', index=False)
        print(f'已输出到 {board_name}30日涨幅排序.xlsx')

    process_board('主板', get_main_board_symbols)
    process_board('创业板', get_chuangye_board_symbols)
    process_board('科创板', get_kechuang_board_symbols)
    process_board('北交所', get_beijiao_board_symbols)

    # 根据生成的文件，生成筛选结果文件
    def generate_filtered_results(board_name, multiplier):
        try:
            df = pd.read_excel(f'{board_name}10日涨幅排序.xlsx')
            filtered_df = df[df['10日涨幅(含今日)%'] * multiplier > 100]
            filtered_df.to_excel(f'{board_name}10日涨幅筛选结果.xlsx', index=False)
            print(f'{board_name}10日涨幅筛选结果.xlsx 已生成')
        except Exception as e:
            print(f"生成{board_name}筛选结果失败: {e}")

    generate_filtered_results('主板', 1.1)
    generate_filtered_results('创业板', 1.2)
    generate_filtered_results('科创板', 1.2)
    generate_filtered_results('北交所', 1.3)

    # 2. 构建table_data
    today = datetime.now()
    start_date = today - pd.tseries.offsets.BDay(10)
    table_data = [
        ["", "", "1. 连续10个交易日内同向异动次数", "", ""],
        ["代码", "简称", "开始日", "截止日", "备注"],
        ["/", "/", "/", "/", "/"],
        ["", "", "2. 连续10个交易日内收盘价涨跌幅偏离值（100%）", "", ""],
        ["代码", "简称", "开始日", "截止日", "备注"],
    ]
    # 分别插入主板、创业板、科创板、北交所
    insert_filtered_data('主板10日涨幅筛选结果.xlsx', 100, table_data, start_date, today)
    insert_filtered_data('创业板10日涨幅筛选结果.xlsx', 100, table_data, start_date, today)
    insert_filtered_data('科创板10日涨幅筛选结果.xlsx', 100, table_data, start_date, today)
    insert_filtered_data('北交所10日涨幅筛选结果.xlsx', 100, table_data, start_date, today)

    # 3. 连续30日异动筛选
    table_data += [
        ["", "", "3. 连续30个交易日内收盘价涨跌幅偏离值（200%）", "", ""],
        ["代码", "简称", "开始日", "截止日", "备注"],
    ]
    found_30d = False
    def generate_filtered_30d_results(board_name, multiplier):
        try:
            df = pd.read_excel(f'{board_name}30日涨幅排序.xlsx')
            filtered_df = df[df['30日涨幅(含今日)%'] * multiplier > 200]
            filtered_df.to_excel(f'{board_name}30日涨幅筛选结果.xlsx', index=False)
            print(f'{board_name}30日涨幅筛选结果.xlsx 已生成')
            return filtered_df
        except Exception as e:
            print(f"生成{board_name}30日筛选结果失败: {e}")
            return pd.DataFrame()
    # 主板1.1，创业板1.2，科创板1.2，北交所1.3
    main_30d = generate_filtered_30d_results('主板', 1.1)
    cyb_30d = generate_filtered_30d_results('创业板', 1.2)
    kcb_30d = generate_filtered_30d_results('科创板', 1.2)
    bj_30d = generate_filtered_30d_results('北交所', 1.3)
    for df, board_name, multiplier in [
        (main_30d, '主板', 1.1),
        (cyb_30d, '创业板', 1.2),
        (kcb_30d, '科创板', 1.2),
        (bj_30d, '北交所', 1.3)
    ]:
        if not df.empty:
            found_30d = True
            for _, row in df.iterrows():
                table_data.append([
                    str(row['股票代码']),
                    str(row['股票简称']),
                    start_date.strftime('%Y-%m-%d'),
                    today.strftime('%Y-%m-%d'),
                    f"30日涨幅{row['30日涨幅(含今日)%']:.2f}%，乘以{multiplier}超异动阈值"
                ])
    if not found_30d:
        table_data.append(["/", "/", "/", "/", "/"])

    # 4. 已异动
    table_data += [
        ["", "", "4. 已异动", "", ""],
        ["代码", "简称", "开始日", "截止日", "备注"],
    ]
    yidong_list = []
    yidong_list += get_yidong_stocks('主板10日涨幅大于90筛选结果.xlsx', start_date, today)
    yidong_list += get_yidong_stocks('创业板10日涨幅大于80筛选结果.xlsx', start_date, today)
    yidong_list += get_yidong_stocks('科创板10日涨幅大于80筛选结果.xlsx', start_date, today)
    yidong_list += get_yidong_stocks('北交所10日涨幅大于70筛选结果.xlsx', start_date, today)
    if yidong_list:
        table_data += yidong_list
    else:
        table_data.append(["/", "/", "/", "/", "/"])

    # 4. 绘制matplotlib表格（保留原有逻辑）
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False
    today = datetime.now().strftime('%m.%d')
    title = f"{today}异动情况"

    nrows = len(table_data)
    ncols = 5

    fig, ax = plt.subplots(figsize=(12, 0.6 * nrows + 1))
    ax.axis('off')

    the_table = plt.table(
        cellText=table_data,
        colWidths=[0.12, 0.18, 0.14, 0.14, 0.42],
        cellLoc='center',
        loc='center'
    )

    # 设置表头和分组行加粗
    for i, row in enumerate(table_data):
        if (row[0].startswith("1.") or row[0].startswith("2.") or row[0].startswith("3.") or row[0].startswith("4.")):
            for j in range(ncols):
                the_table[i, j].set_text_props(weight='bold', fontsize=13)
                the_table[i, j].set_facecolor('#e0f7fa')
        elif row[0] in ["代码", "简称", "开始日", "截止日", "备注"]:
            for j in range(ncols):
                the_table[i, j].set_text_props(weight='bold', fontsize=12)
                the_table[i, j].set_facecolor('#b2dfdb')
        else:
            for j in range(ncols):
                the_table[i, j].set_text_props(fontsize=11)
                the_table[i, j].set_facecolor('#ffffff' if i % 2 == 0 else '#f8f9fa')

    the_table.auto_set_font_size(False)
    the_table.scale(1, 1.3)

    plt.title(title, fontsize=18, weight='bold', pad=20)
    plt.tight_layout()
    plt.savefig('异动情况统计表_matplotlib.png', bbox_inches='tight', dpi=200)
    plt.show()

    


