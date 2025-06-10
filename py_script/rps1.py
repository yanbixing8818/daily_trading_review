import pandas as pd
import core.tablestructure as tbs
import core.database as mdb
from datetime import datetime
import core.trade_time as trade_time

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database


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


def RPS(N=10):
    """
    计算每个股票今天收盘价相对于N个交易日前收盘价的涨幅（RPS），并保存到rps_N表，包含归一化排序字段。
    区间为（end_date_str, start_date_str]。
    """
    start_date_str, end_date_str = get_recent_trade_range(N)
    print(f"计算{N}日RPS，区间为（{end_date_str}, {start_date_str}]")
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
        # 读取表数据，取区间（end_date_str, start_date_str]，按date升序排列
        sql = f"SELECT date, close FROM `{table_name}` WHERE close IS NOT NULL AND date > '{end_date_str}' AND date <= '{start_date_str}' ORDER BY date ASC"
        rows = mdb.executeSqlFetch(sql)
        if not rows or len(rows) < 2:
            continue
        df = pd.DataFrame(rows, columns=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        if len(df) < 2:
            continue
        # 区间内第一条和最后一条
        close_N_days_ago = df.iloc[0]["close"]
        close_today = df.iloc[-1]["close"]
        if close_N_days_ago > 0:
            rps = close_today / close_N_days_ago - 1
        else:
            rps = None
        stock_name = code_map.get(table_name, "")
        results.append((table_name, stock_name, rps, df.iloc[-1]["date"], df.iloc[0]["date"]))
    
    # 保存到SQL表
    df_n = pd.DataFrame(results, columns=["code", "name", f"rps_{N}", f"today_date", f"N_days_ago_date"])
    df_n["code"] = df_n["code"].astype(str).str.zfill(6)
    
    # 归一化排序
    if not df_n.empty:
        rps_col = f"rps_{N}"
        df_n = df_n.sort_values(by=rps_col, ascending=False).reset_index(drop=True)
        minv = df_n[rps_col].min()
        maxv = df_n[rps_col].max()
        if maxv > minv:
            df_n[f"rps_{N}_rank"] = ((df_n[rps_col] - minv) / (maxv - minv) * 100).round(2)
        else:
            df_n[f"rps_{N}_rank"] = 100.0
    mdb.executeSql(f"DROP TABLE IF EXISTS rps_{N}")
    df_n.to_sql(f"rps_{N}", mdb.engine(), if_exists="replace", index=False)
    print(f"已保存到数据库表 rps_{N}")


if __name__ == "__main__":
    RPS(5)
    # RPS(10)
    # RPS(20)


