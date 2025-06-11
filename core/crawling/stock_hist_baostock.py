import baostock as bs
import pandas as pd
import core.tablestructure as tbs
import core.database as mdb
from datetime import datetime
import logging
import core.trade_time as trade_time
import numpy as np
from core.utils import get_recent_trade_range

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database



# 获取一个股票从start_date到end_date的历史数据
def get_a_hist_k_data(baostock_code, start_date, end_date):  # adjustflag：复权类型，默认不复权：3；1：后复权；2：前复权。
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
        frequency="d", adjustflag="2")  
    print(rs.error_code)
    print(rs.error_msg)
    # 获取具体的信息
    result_list = []
    while (rs.error_code == '0') & rs.next():
        result_list.append(rs.get_row_data())
    result = pd.DataFrame(result_list, columns=rs.fields)
    print(f"{baostock_code} 从{start_date}到{end_date}的历史数据:")
    print(result)
    # 登出系统
    bs.logout()
    return result


# 获取所有股票从start_date到end_date的历史数据，并保存到数据库
def get_all_hist_k_data_and_save(start_date_str, end_date_str):
    try:
        table_name = tbs.TABLE_CN_BAOSTOCK_CODE_MAP['name']
        sql = f"SELECT name, code, baostock_mapped_code FROM `{table_name}`"
        rows = mdb.executeSqlFetch(sql)
        if rows:
            print(f"{table_name}表内容：")
            for row in rows:
                name, code, baostock_mapped_code = row
                print(row)
                # 获取30日历史数据
                hist_df = get_a_hist_k_data(baostock_mapped_code, start_date_str, end_date_str)
                if hist_df is not None and not hist_df.empty:
                    # 去重，确保date和code都相同只保留一行
                    hist_df = hist_df.drop_duplicates(subset=['date', 'code'], keep='last').reset_index(drop=True)
                    hist_table_name = code  # 直接用原始code作为表名
                    # 删除老数据（区间内）
                    if mdb.checkTableIsExist(hist_table_name):
                        del_sql = f"DELETE FROM `{hist_table_name}` WHERE `date` > '{start_date_str}' AND `date` <= '{end_date_str}'"
                        mdb.executeSql(del_sql)
                        cols_type = None
                    else:
                        cols_type = None  # 字段类型自动推断
                    # 插入新数据，唯一键date,code
                    try:
                        mdb.insert_db_from_df(hist_df, hist_table_name, cols_type, False, "`date`,`code`")
                        print(f"历史数据已保存到表 {hist_table_name}")
                    except Exception as e:
                        logging.error(f"保存历史数据到表 {hist_table_name} 失败: {e}")
        else:
            print(f"{table_name}表无数据。")
    except Exception as e:
        logging.error(f"read_baostock_code_map_table处理异常：{e}")




if __name__ == "__main__":
    # df = get_a_hist_k_data("sz.000001", "2025-06-09", "2025-06-10")
    # print(df)

    today = datetime.now().date()
    start_date_str, end_date_str = get_recent_trade_range(today, 1)
    print(start_date_str, end_date_str)
    get_all_hist_k_data_and_save(start_date_str, end_date_str)


    # df = get_a_hist_k_data("sz.000001", "2025-06-09", "2025-06-10")
    # print(df)


