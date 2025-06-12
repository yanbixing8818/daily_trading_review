import pandas as pd
import core.tablestructure as tbs
import core.database as mdb
from datetime import datetime
import core.trade_time as trade_time
from core.utils import get_recent_trade_range

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database


# 计算N日RPS，该函数需要传入date和N，返回date前N个交易日的RPS数据，并保存到rps_N表中。
def RPS(date,N=10):
    """
    计算每个股票今天收盘价相对于N个交易日前收盘价的涨幅（RPS），并保存到rps_N表，包含归一化排序字段。
    区间为（end_date_str, start_date_str]。
    """
    start_date_str, end_date_str = get_recent_trade_range(date, N)
    print(f"计算{N}日RPS，区间为（{start_date_str}, {end_date_str}]")
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
        # 读取表数据，取区间（start_date_str, end_date_str]，按date升序排列
        # 1. 构造SQL语句，从当前股票表（table_name）中选取close不为NULL且日期在(start_date_str, end_date_str]区间内的数据，按日期升序排列。
        sql = f"SELECT date, close FROM `{table_name}` WHERE close IS NOT NULL AND date > '{start_date_str}' AND date <= '{end_date_str}' ORDER BY date ASC"
        # 2. 执行SQL查询，获取结果rows。
        rows = mdb.executeSqlFetch(sql)
        # 3. 如果没有数据或数据量小于2，跳过该股票。
        if not rows or len(rows) < 2:
            continue
        # 4. 将查询结果转为DataFrame，并确保close列为数值型，去除close为NaN的行。
        df = pd.DataFrame(rows, columns=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        # 5. 再次检查数据量，若小于2则跳过。
        if len(df) < 2:
            continue
        # 6. 取区间内第一天（N天前）和最后一天（今天）的收盘价。
        close_N_days_ago = df.iloc[0]["close"]
        close_today = df.iloc[-1]["close"]
        # 7. 计算区间涨幅，如果N天前收盘价大于0则计算，否则为None。
        if close_N_days_ago > 0:
            rps = close_today / close_N_days_ago - 1
        else:
            rps = None
        # 8. 获取股票名称，并将结果（股票代码、名称、RPS、今天日期、N天前日期）添加到results列表。
        stock_name = code_map.get(table_name, "")
        results.append((table_name, stock_name, rps, df.iloc[-1]["date"], df.iloc[0]["date"]))
    
    # 保存到df中
    df_n = pd.DataFrame(results, columns=["code", "name", f"rps_{N}", f"today_date", f"N_days_ago_date"])
    df_n["code"] = df_n["code"].astype(str).str.zfill(6)
    
    # 归一化排序并保存到数据库
    if not df_n.empty:
        rps_col = f"rps_{N}"
        # 按涨幅降序排序，得到排名（1为第一名）
        df_n = df_n.sort_values(by=rps_col, ascending=False).reset_index(drop=True)
        df_n[f"rps_{N}_rank_num"] = df_n.index + 1  # 排名，1为第一名
        total = len(df_n)
        # 用排名归一化，第一名100，最后一名0
        if total > 1:
            df_n[f"rps_{N}_rank"] = ((total - df_n[f"rps_{N}_rank_num"]) / (total - 1) * 100).round(2)
        else:
            df_n[f"rps_{N}_rank"] = 100.0
    mdb.executeSql(f"DROP TABLE IF EXISTS rps_{N}")
    df_n.to_sql(f"rps_{N}", mdb.engine(), if_exists="replace", index=False)
    print(f"已保存到数据库表 rps_{N}")


if __name__ == "__main__":
    date = datetime(2025, 6, 11).date()
    RPS(date,5)
    # RPS(date,10)
    # RPS(date,20)


