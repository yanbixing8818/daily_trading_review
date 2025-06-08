import baostock as bs
import pandas as pd
import core.tablestructure as tbs
import core.crawling.stock_hist_em as she
import core.database as mdb
import datetime
import logging
import core.trade_time as trade_time

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
    today = datetime.datetime.now().date()
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

if __name__ == "__main__":
    table_name = tbs.TABLE_CN_BAOSTOCK_CODE_MAP['name']
    if not mdb.checkTableIsExist(table_name):
        create_baostock_code_map_table()
    read_baostock_code_map_table()