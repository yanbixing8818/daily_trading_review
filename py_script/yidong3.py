import baostock as bs
import pandas as pd
import core.tablestructure as tbs
import core.crawling.stock_hist_em as she
import core.database as mdb
from datetime import datetime
import logging
import core.trade_time as trade_time
import csv
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from matplotlib.table import Table
import numpy as np

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database

def get_history_k_data(baostock_code, start_date, end_date):
    # 登陆系统
    lg = bs.login()
    # 显示登陆返回信息
    print(lg.error_code)
    print(lg.error_msg)
    # 查询历史K线数据
    rs = bs.query_history_k_data_plus(
        baostock_code,
        "date,code,open,high,low,close,volume,amount,adjustflag",
        start_date=start_date, end_date=end_date,
        frequency="d", adjustflag="3")
    print(rs.error_code)
    print(rs.error_msg)
    # 获取具体的信息
    result_list = []
    while (rs.error_code == '0') & rs.next():
        result_list.append(rs.get_row_data())
    result = pd.DataFrame(result_list, columns=rs.fields)
    print(f"{baostock_code} 近30日历史数据:")
    print(result)
    # 登出系统
    bs.logout()
    return result

def add_prefix(code):
    code = str(code)
    if code.startswith(('6', '9')):
        return 'sh.' + code
    elif code.startswith(('0', '3', '2')):
        return 'sz.' + code
    else:
        return code  # 若无法识别则原样返回

def create_baostock_code_map_table():
    try:
        # #获取所有A股股票数据
        # df = she.stock_zh_a_spot_em()
        # if df is None or len(df.index) == 0:
        #     print("未从东方财富获取到A股股票数据")
        #     df = pd.read_csv('./all_a_stock_spot.csv')
        # print(df)

        df = pd.read_csv('./data/all_a_stock_spot.csv')

        print(df.columns)
        df.rename(columns={'代码': 'code', '名称': 'name'}, inplace=True)
        df['code'] = df['code'].astype(str).str.zfill(6)
        df['baostock_mapped_code'] = df['code'].apply(add_prefix)
        # 只保留name, code, baostock_mapped_code三列
        df = df[['name', 'code', 'baostock_mapped_code']]
        table_name = tbs.TABLE_CN_BAOSTOCK_CODE_MAP['name']
        cols_type = tbs.get_field_types(tbs.TABLE_CN_BAOSTOCK_CODE_MAP['columns'])
        # 先清空表
        if mdb.checkTableIsExist(table_name):
            mdb.executeSql(f"DELETE FROM `{table_name}`")
        # 插入数据
        mdb.insert_db_from_df(df, table_name, cols_type, False, "`code`")
        print(f"{table_name}表已创建并写入{len(df)}条数据")
    except Exception as e:
        logging.error(f"create_baostock_code_map_table处理异常：{e}")

def get_recent_trade_range(n=30):
    """
    获取最近n个交易日区间，返回(start_date_str, end_date_str)
    start_date为今天（如非交易日则为最近一个交易日），end_date为start_date往前推n个交易日。
    """
    today = datetime.now().date()
    if not trade_time.is_trade_date(today):
        start_date = trade_time.get_previous_trade_date(today)
    else:
        start_date = today
    trade_dates = list(sorted(trade_time.stock_trade_date().get_data()))
    start_idx = trade_dates.index(start_date)
    if start_idx < n:
        end_date = trade_dates[0]
    else:
        end_date = trade_dates[start_idx - n]
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    return start_date_str, end_date_str

def read_baostock_code_map_table():
    try:
        table_name = tbs.TABLE_CN_BAOSTOCK_CODE_MAP['name']
        sql = f"SELECT name, code, baostock_mapped_code FROM `{table_name}`"
        rows = mdb.executeSqlFetch(sql)
        if rows:
            print(f"{table_name}表内容：")
            start_date_str, end_date_str = get_recent_trade_range(30)
            for row in rows:
                name, code, baostock_mapped_code = row
                print(row)
                # 获取30日历史数据
                hist_df = get_history_k_data(baostock_mapped_code, end_date_str, start_date_str)
                if hist_df is not None and not hist_df.empty:
                    # 以股票代码为表名保存
                    hist_table_name = code  # 直接用原始code作为表名
                    # 字段类型自动推断
                    try:
                        mdb.insert_db_from_df(hist_df, hist_table_name, None, False, "`date`")
                        print(f"历史数据已保存到表 {hist_table_name}")
                    except Exception as e:
                        logging.error(f"保存历史数据到表 {hist_table_name} 失败: {e}")
        else:
            print(f"{table_name}表无数据。")
    except Exception as e:
        logging.error(f"read_baostock_code_map_table处理异常：{e}")

def calc_max_rise_for_all_stocks():
    """
    遍历所有股票历史表，分别计算每个股票的30日、10日最大涨幅。
    最大涨幅 = 期间内最高收盘/最低收盘 - 1
    结果分别按30日和10日最大涨幅排序，保存到数据库表。
    """
    # 获取所有表名
    sql = f"SELECT table_name FROM information_schema.tables WHERE table_schema='{mdb.db_database}'"
    tables = mdb.executeSqlFetch(sql)
    if not tables:
        print("未获取到表名")
        return
    # 获取股票代码和名称的映射
    code_map = {}
    map_table = tbs.TABLE_CN_BAOSTOCK_CODE_MAP['name']
    map_rows = mdb.executeSqlFetch(f"SELECT code, name FROM `{map_table}`")
    if map_rows:
        code_map = {str(code): name for code, name in map_rows}
    results = []
    for (table_name,) in tables:
        # 只处理6位数字的表名
        if not (isinstance(table_name, str) and len(table_name) == 6 and table_name.isdigit()):
            continue
        # 读取表数据
        sql = f"SELECT date, close FROM `{table_name}` ORDER BY date DESC LIMIT 30"
        rows = mdb.executeSqlFetch(sql)
        if not rows or len(rows) < 2:
            continue
        # 30日最大涨幅及日期
        closes_30 = [(r[0], float(r[1])) for r in rows if r[1] is not None]
        if len(closes_30) < 2:
            continue
        max_30_val = max(closes_30, key=lambda x: x[1])
        min_30_val = min(closes_30, key=lambda x: x[1])
        rise_30 = (max_30_val[1] / min_30_val[1] - 1) if min_30_val[1] > 0 else None
        max_30_date = max_30_val[0]
        min_30_date = min_30_val[0]
        # 10日最大涨幅及日期
        closes_10 = closes_30[:10] if len(closes_30) >= 10 else closes_30
        if len(closes_10) >= 2:
            max_10_val = max(closes_10, key=lambda x: x[1])
            min_10_val = min(closes_10, key=lambda x: x[1])
            rise_10 = (max_10_val[1] / min_10_val[1] - 1) if min_10_val[1] > 0 else None
            max_10_date = max_10_val[0]
            min_10_date = min_10_val[0]
        else:
            rise_10 = None
            max_10_date = None
            min_10_date = None
        stock_name = code_map.get(table_name, "")
        results.append((table_name, stock_name, rise_30, max_30_date, min_30_date, rise_10, max_10_date, min_10_date))
    # 打印结果
    print("股票代码 | 股票名称 | 30日最大涨幅 | 最高价日 | 最低价日 | 10日最大涨幅 | 最高价日 | 最低价日")
    for code, name, r30, dmax30, dmin30, r10, dmax10, dmin10 in results:
        print(f"{code} | {name} | {r30:.2%} | {dmax30} | {dmin30} | {r10:.2%} | {dmax10} | {dmin10}")
    # 保存到数据库表
    df = pd.DataFrame(results, columns=["code", "name", "max_rise_30d", "max_30d_date", "min_30d_date", "max_rise_10d", "max_10d_date", "min_10d_date"])
    df["code"] = df["code"].astype(str).str.zfill(6)
    df_30 = df.sort_values(by="max_rise_30d", ascending=False)[["code", "name", "max_rise_30d", "max_30d_date", "min_30d_date"]].copy()
    df_10 = df.sort_values(by="max_rise_10d", ascending=False)[["code", "name", "max_rise_10d", "max_10d_date", "min_10d_date"]].copy()
    df_30["code"] = df_30["code"].astype(str).str.zfill(6)
    df_10["code"] = df_10["code"].astype(str).str.zfill(6)
    # 保存到SQL表
    mdb.executeSql(f"DROP TABLE IF EXISTS max_rise_30d")
    mdb.executeSql(f"DROP TABLE IF EXISTS max_rise_10d")
    df_30.to_sql("max_rise_30d", mdb.engine(), if_exists="replace", index=False)
    df_10.to_sql("max_rise_10d", mdb.engine(), if_exists="replace", index=False)
    print("已保存到数据库表 max_rise_30d 和 max_rise_10d")

def detect_main_board_abnormal():
    """
    检测主板异动：读取max_rise_10d表，找出10日涨幅超过100%的股票，打印其信息，并备注（日期）已经严重异动。
    也筛选今日收盘价大于10日前最低价*2的主板股票。
    """
    try:
        df = pd.read_sql("SELECT * FROM max_rise_10d", mdb.engine())
    except Exception as e:
        print(f"读取max_rise_10d表失败: {e}")
        return
    # 只筛选主板股票
    main_board_prefix = ("600", "601", "603", "605", "000", "001", "002", "003")
    df = df[df["code"].astype(str).str.zfill(6).str.startswith(main_board_prefix)]

    # 过滤10日涨幅超过100%的
    abnormal = df[df["max_rise_10d"] > 1]
    today = datetime.now().strftime("%Y-%m-%d")
    if not abnormal.empty:
        for _, row in abnormal.iterrows():
            print(f"股票代码: {row['code']} | 名称: {row['name']} | 10日最大涨幅: {row['max_rise_10d']:.2%} | 最高价日: {row['max_10d_date']} | 最低价日: {row['min_10d_date']} | {today} 已经严重异动")
    else:
        print("无10日涨幅超过100%的主板股票")
    
    # 进一步筛选 (今日收盘价 * 1.1 / 10日最低价) > 100% 的主板股票（排除已在abnormal中的票）
    abnormal_codes = set(abnormal["code"].astype(str).str.zfill(6))
    for _, row in df.iterrows():
        code = str(row['code']).zfill(6)
        if code in abnormal_codes:
            continue  # 已经在10日涨幅>100%的票中，跳过
        min_10d_date = row['min_10d_date']
        try:
            # 取最新一条收盘价
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            # 取10日区间最低价
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_10d_date}' AND close IS NOT NULL LIMIT 1"
            min_10d = mdb.executeSqlFetch(sql)
            if not min_10d or min_10d[0][0] is None:
                continue
            min_10d_close = float(min_10d[0][0])
            # 判断 (今日收盘价 * 1.1 / 10日最低价) > 2
            if min_10d_close > 0 and (latest_close * 1.1 / min_10d_close) > 2:
                # 计算涨幅2
                zf2 = (min_10d_close * 2 - latest_close) / latest_close
                print(f"股票代码: {row['code']} | 名称: {row['name']} | 最新收盘价: {latest_close} | 10日前最低价: {min_10d_close} | 10日前最低价日: {min_10d_date} | 当前涨幅: {(latest_close / min_10d_close - 1):.2%} | {today} 如果明天涨幅{zf2:.2%}，将严重异动")
        except Exception as e:
            print(f"处理股票{code}时异常: {e}")

def detect_gem_and_star_board_abnormal():
    """
    检测创业板+科创板异动：
    1. 10日涨幅超过100%的创业板/科创板股票
    2. (今日收盘价 * 1.2 / 10日最低价) > 2 的创业板/科创板股票（排除已在abnormal中的票）
    """
    try:
        df = pd.read_sql("SELECT * FROM max_rise_10d", mdb.engine())
    except Exception as e:
        print(f"读取max_rise_10d表失败: {e}")
        return
    # 创业板（300/301开头），科创板（688开头）
    gem_star_prefix = ("300", "301", "688")
    df = df[df["code"].astype(str).str.zfill(6).str.startswith(gem_star_prefix)]

    # 10日涨幅超过100%
    abnormal = df[df["max_rise_10d"] > 1]
    today = datetime.now().strftime("%Y-%m-%d")
    if not abnormal.empty:
        for _, row in abnormal.iterrows():
            print(f"[创业/科创] 股票代码: {row['code']} | 名称: {row['name']} | 10日最大涨幅: {row['max_rise_10d']:.2%} | 最高价日: {row['max_10d_date']} | 最低价日: {row['min_10d_date']} | 当前涨幅: {row['max_rise_10d']:.2%} | {today} 已经严重异动")
    else:
        print("无10日涨幅超过100%的创业/科创板股票")

    # 进一步筛选 (今日收盘价 * 1.2 / 10日最低价) > 2，排除已在abnormal中的票
    abnormal_codes = set(abnormal["code"].astype(str).str.zfill(6))
    for _, row in df.iterrows():
        code = str(row['code']).zfill(6)
        if code in abnormal_codes:
            continue
        min_10d_date = row['min_10d_date']
        try:
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_10d_date}' AND close IS NOT NULL LIMIT 1"
            min_10d = mdb.executeSqlFetch(sql)
            if not min_10d or min_10d[0][0] is None:
                continue
            min_10d_close = float(min_10d[0][0])
            if min_10d_close > 0 and (latest_close * 1.2 / min_10d_close) > 2:
                zf2 = (min_10d_close * 2 - latest_close) / latest_close
                print(f"[创业/科创] 股票代码: {row['code']} | 名称: {row['name']} | 最新收盘价: {latest_close} | 10日前最低价: {min_10d_close} | 10日前最低价日: {min_10d_date} | 当前涨幅: {(latest_close / min_10d_close - 1):.2%} | 明日涨幅{zf2:.2%}将严重异动")
        except Exception as e:
            print(f"处理股票{code}时异常: {e}")

def detect_main_board_abnormal_30d():
    """
    检测主板30日异动：读取max_rise_30d表，找出30日涨幅超过200%的股票，打印其信息，并备注（日期）已经严重异动。
    也筛选 (今日收盘价 * 1.1 / 30日最低价) > 2 的主板股票（排除已在abnormal中的票），并给出明天涨2%到2倍的提示。
    """
    try:
        df = pd.read_sql("SELECT * FROM max_rise_30d", mdb.engine())
    except Exception as e:
        print(f"读取max_rise_30d表失败: {e}")
        return
    main_board_prefix = ("600", "601", "603", "605", "000", "001", "002", "003")
    df = df[df["code"].astype(str).str.zfill(6).str.startswith(main_board_prefix)]
    abnormal = df[df["max_rise_30d"] > 2]
    today = datetime.now().strftime("%Y-%m-%d")
    if not abnormal.empty:
        for _, row in abnormal.iterrows():
            print(f"[30日] 股票代码: {row['code']} | 名称: {row['name']} | 30日最大涨幅: {row['max_rise_30d']:.2%} | 最高价日: {row['max_30d_date']} | 最低价日: {row['min_30d_date']} | 当前涨幅: {row['max_rise_30d']:.2%} | {today} 已经严重异动")
    else:
        print("无30日涨幅超过200%的主板股票")
    abnormal_codes = set(abnormal["code"].astype(str).str.zfill(6))
    for _, row in df.iterrows():
        code = str(row['code']).zfill(6)
        if code in abnormal_codes:
            continue
        min_30d_date = row['min_30d_date']
        try:
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_30d_date}' AND close IS NOT NULL LIMIT 1"
            min_30d = mdb.executeSqlFetch(sql)
            if not min_30d or min_30d[0][0] is None:
                continue
            min_30d_close = float(min_30d[0][0])
            # 判断 (今日收盘价 * 1.1 / 30日最低价) > 3 （200%是今日收盘价是30日最低价的3倍）
            if min_30d_close > 0 and (latest_close * 1.1 / min_30d_close) > 3:
                zf2 = (min_30d_close * 2 - latest_close) / latest_close
                print(f"[30日] 股票代码: {row['code']} | 名称: {row['name']} | 最新收盘价: {latest_close} | 30日前最低价: {min_30d_close} | 30日前最低价日: {min_30d_date} | 当前涨幅: {(latest_close / min_30d_close - 1):.2%} | 明天涨幅{zf2:.2%}，将严重异动")
        except Exception as e:
            print(f"处理股票{code}时异常: {e}")

def detect_gem_and_star_board_abnormal_30d():
    """
    检测创业板+科创板30日异动：
    1. 30日涨幅超过200%的创业板/科创板股票
    2. (今日收盘价 * 1.2 / 30日最低价) > 2 的创业板/科创板股票（排除已在abnormal中的票），并给出明天涨2%到2倍的提示。
    """
    try:
        df = pd.read_sql("SELECT * FROM max_rise_30d", mdb.engine())
    except Exception as e:
        print(f"读取max_rise_30d表失败: {e}")
        return
    gem_star_prefix = ("300", "301", "688")
    df = df[df["code"].astype(str).str.zfill(6).str.startswith(gem_star_prefix)]
    abnormal = df[df["max_rise_30d"] > 2]
    today = datetime.now().strftime("%Y-%m-%d")
    if not abnormal.empty:
        for _, row in abnormal.iterrows():
            print(f"[创业/科创-30日] 股票代码: {row['code']} | 名称: {row['name']} | 30日最大涨幅: {row['max_rise_30d']:.2%} | 最高价日: {row['max_30d_date']} | 最低价日: {row['min_30d_date']} | 当前涨幅: {row['max_rise_30d']:.2%} | {today} 已经严重异动")
    else:
        print("无30日涨幅超过200%的创业/科创板股票")
    abnormal_codes = set(abnormal["code"].astype(str).str.zfill(6))
    for _, row in df.iterrows():
        code = str(row['code']).zfill(6)
        if code in abnormal_codes:
            continue
        min_30d_date = row['min_30d_date']
        try:
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_30d_date}' AND close IS NOT NULL LIMIT 1"
            min_30d = mdb.executeSqlFetch(sql)
            if not min_30d or min_30d[0][0] is None:
                continue
            min_30d_close = float(min_30d[0][0])
            if min_30d_close > 0 and (latest_close * 1.2 / min_30d_close) > 3:
                zf2 = (min_30d_close * 2 - latest_close) / latest_close
                print(f"[创业/科创-30日] 股票代码: {row['code']} | 名称: {row['name']} | 最新收盘价: {latest_close} | 30日前最低价: {min_30d_close} | 30日前最低价日: {min_30d_date} | 当前涨幅: {(latest_close / min_30d_close - 1):.2%} | 明日涨幅{zf2:.2%}，将严重异动")
        except Exception as e:
            print(f"处理股票{code}时异常: {e}")

def export_abnormal_tables():
    """
    整理输出10日异动榜和30日异动榜，包含：code，名称，最大涨幅，最低价日，最高价日，备注。
    """
    import pandas as pd
    # 10日异动榜
    try:
        df10 = pd.read_sql("SELECT * FROM max_rise_10d", mdb.engine())
    except Exception as e:
        print(f"读取max_rise_10d表失败: {e}")
        return
    # 只保留最高价日>最低价日的记录
    df10 = df10[df10["max_10d_date"] > df10["min_10d_date"]].copy()
    abnormal_10 = df10[df10["max_rise_10d"] > 1].copy()
    abnormal_10["备注"] = "已严重异动"
    # 检查zf2相关股票（主板、创业板、科创板）
    zf2_rows_10 = []
    for _, row in df10.iterrows():
        code = str(row['code']).zfill(6)
        if code in set(abnormal_10["code"].astype(str).str.zfill(6)):
            continue
        min_10d_date = row['min_10d_date']
        max_10d_date = row['max_10d_date']
        # 只考虑最高价日在最低价日之后的
        if max_10d_date <= min_10d_date:
            continue
        try:
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_10d_date}' AND close IS NOT NULL LIMIT 1"
            min_10d = mdb.executeSqlFetch(sql)
            if not min_10d or min_10d[0][0] is None:
                continue
            min_10d_close = float(min_10d[0][0])
            is_main = code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))
            is_gem_star = code.startswith(("300", "301", "688"))
            if is_main and min_10d_close > 0 and (latest_close * 1.1 / min_10d_close) > 2:
                zf2 = (min_10d_close * 2 - latest_close) / latest_close
                zf2_rows_10.append({
                    "code": code,
                    "name": row["name"],
                    "最大涨幅": latest_close / min_10d_close - 1,
                    "最低价日": min_10d_date,
                    "最高价日": max_10d_date,
                    "备注": f"明日涨{zf2:.2%}将严重异动"
                })
            elif is_gem_star and min_10d_close > 0 and (latest_close * 1.2 / min_10d_close) > 2:
                zf2 = (min_10d_close * 2 - latest_close) / latest_close
                zf2_rows_10.append({
                    "code": code,
                    "name": row["name"],
                    "最大涨幅": latest_close / min_10d_close - 1,
                    "最低价日": min_10d_date,
                    "最高价日": max_10d_date,
                    "备注": f"明日涨{zf2:.2%}将严重异动"
                })
        except Exception as e:
            continue
    out10 = abnormal_10[["code", "name", "max_rise_10d", "min_10d_date", "max_10d_date", "备注"]].copy()
    out10 = out10.rename(columns={"max_rise_10d": "最大涨幅", "min_10d_date": "最低价日", "max_10d_date": "最高价日"})
    if zf2_rows_10:
        out10 = pd.concat([out10, pd.DataFrame(zf2_rows_10)], ignore_index=True)
    # 格式化最大涨幅为百分比字符串
    out10["最大涨幅"] = out10["最大涨幅"].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "")

    # 30日异动榜
    try:
        df30 = pd.read_sql("SELECT * FROM max_rise_30d", mdb.engine())
    except Exception as e:
        print(f"读取max_rise_30d表失败: {e}")
        return
    df30 = df30[df30["max_30d_date"] > df30["min_30d_date"]].copy()
    abnormal_30 = df30[df30["max_rise_30d"] > 2].copy()
    abnormal_30["备注"] = "已严重异动"
    zf2_rows_30 = []
    for _, row in df30.iterrows():
        code = str(row['code']).zfill(6)
        if code in set(abnormal_30["code"].astype(str).str.zfill(6)):
            continue
        min_30d_date = row['min_30d_date']
        max_30d_date = row['max_30d_date']
        if max_30d_date <= min_30d_date:
            continue
        try:
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_30d_date}' AND close IS NOT NULL LIMIT 1"
            min_30d = mdb.executeSqlFetch(sql)
            if not min_30d or min_30d[0][0] is None:
                continue
            min_30d_close = float(min_30d[0][0])
            is_main = code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))
            is_gem_star = code.startswith(("300", "301", "688"))
            if is_main and min_30d_close > 0 and (latest_close * 1.1 / min_30d_close) > 3:
                zf2 = (min_30d_close * 2 - latest_close) / latest_close
                zf2_rows_30.append({
                    "code": code,
                    "name": row["name"],
                    "最大涨幅": latest_close / min_30d_close - 1,
                    "最低价日": min_30d_date,
                    "最高价日": max_30d_date,
                    "备注": f"明日涨{zf2:.2%}将严重异动"
                })
            elif is_gem_star and min_30d_close > 0 and (latest_close * 1.2 / min_30d_close) > 3:
                zf2 = (min_30d_close * 2 - latest_close) / latest_close
                zf2_rows_30.append({
                    "code": code,
                    "name": row["name"],
                    "最大涨幅": latest_close / min_30d_close - 1,
                    "最低价日": min_30d_date,
                    "最高价日": max_30d_date,
                    "备注": f"明日涨{zf2:.2%}将严重异动"
                })
        except Exception as e:
            continue
    out30 = abnormal_30[["code", "name", "max_rise_30d", "min_30d_date", "max_30d_date", "备注"]].copy()
    out30 = out30.rename(columns={"max_rise_30d": "最大涨幅", "min_30d_date": "最低价日", "max_30d_date": "最高价日"})
    if zf2_rows_30:
        out30 = pd.concat([out30, pd.DataFrame(zf2_rows_30)], ignore_index=True)
    out30["最大涨幅"] = out30["最大涨幅"].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "")
    # 输出到同一张图（上下排，备注列加宽）
    nrows = 2
    ncols = 1
    row_num_10 = len(out10)
    row_num_30 = len(out30)
    col_num_10 = len(out10.columns)
    col_num_30 = len(out30.columns)
    # 备注列宽度加大
    base_col_width = 1.2
    remark_col_width = 4.5  # 备注列宽度
    # 计算宽度：普通列*数量+备注列
    fig_width_10 = base_col_width * (col_num_10 - 1) + remark_col_width
    fig_width_30 = base_col_width * (col_num_30 - 1) + remark_col_width
    fig_width = max(10, fig_width_10, fig_width_30)
    fig_height = max(6, row_num_10 * 0.5 + row_num_30 * 0.5 + 3)
    fig, axes = plt.subplots(nrows, ncols, figsize=(fig_width, fig_height))
    fig.suptitle(f'{datetime.now().date()}异动情况', fontsize=18)
    axes = axes if isinstance(axes, (list, np.ndarray)) else [axes]

    # 10日榜
    axes[0].axis('off')
    tbl10 = axes[0].table(cellText=out10.values, colLabels=out10.columns, loc='center', cellLoc='center')
    tbl10.auto_set_font_size(False)
    tbl10.set_fontsize(12)
    tbl10.scale(1.2, 1.2)
    axes[0].set_title('10日异动榜', fontsize=14)
    # 调整备注列宽
    for key, cell in tbl10.get_celld().items():
        if key[1] == out10.columns.get_loc("备注"):
            cell.set_width(remark_col_width / fig_width)
        else:
            cell.set_width(base_col_width / fig_width)

    # 30日榜
    axes[1].axis('off')
    tbl30 = axes[1].table(cellText=out30.values, colLabels=out30.columns, loc='center', cellLoc='center')
    tbl30.auto_set_font_size(False)
    tbl30.set_fontsize(12)
    tbl30.scale(1.2, 1.2)
    axes[1].set_title('30日异动榜', fontsize=14)
    for key, cell in tbl30.get_celld().items():
        if key[1] == out30.columns.get_loc("备注"):
            cell.set_width(remark_col_width / fig_width)
        else:
            cell.set_width(base_col_width / fig_width)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig('abnormal_both.png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    print("已保存10日+30日异动榜图片 abnormal_both.png")
    return out10, out30

if __name__ == "__main__":
    # table_name = tbs.TABLE_CN_BAOSTOCK_CODE_MAP['name']
    # if not mdb.checkTableIsExist(table_name):
    #     create_baostock_code_map_table()
    # read_baostock_code_map_table()
    # calc_max_rise_for_all_stocks()
    detect_main_board_abnormal()
    detect_gem_and_star_board_abnormal()
    detect_main_board_abnormal_30d()
    detect_gem_and_star_board_abnormal_30d()
    export_abnormal_tables()