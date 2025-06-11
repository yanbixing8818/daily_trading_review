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
from core.utils import get_recent_trade_range

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database



def calc_max_rise(date, N=30):
    """
    读取所有表名，读取每个表内从start_date_str到end_date_str区间内的数据，
    计算最大涨幅（最高价日>最低价日），保存到新生成的表max_rise_custom。
    同时保存最高价日和最低价日对应的收盘价。
    """
    start_date_str, end_date_str = get_recent_trade_range(date, N)
    print(f"计算{N}日最大涨幅，区间为（{start_date_str}, {end_date_str}]")

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
        # 读取表数据，取区间（start_date_str, end_date_str]，按日期升序排列
        sql = f"SELECT date, close FROM `{table_name}` WHERE close IS NOT NULL AND date > '{start_date_str}' AND date <= '{end_date_str}' ORDER BY date ASC"
        rows = mdb.executeSqlFetch(sql)
        if not rows or len(rows) < 2:
            continue
        df = pd.DataFrame(rows, columns=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        if len(df) < 2:
            continue
        # 计算最大涨幅（最高价日>最低价日）
        max_rise = -float('inf')
        min_date = max_date = None
        min_close = max_close = None
        for i in range(len(df)):
            for j in range(i+1, len(df)):
                if df.iloc[j]['close'] > 0 and df.iloc[i]['close'] > 0:
                    rise = df.iloc[j]['close'] / df.iloc[i]['close'] - 1
                    if rise > max_rise:
                        max_rise = rise
                        min_date = df.iloc[i]['date']
                        max_date = df.iloc[j]['date']
                        min_close = df.iloc[i]['close']
                        max_close = df.iloc[j]['close']
        max_rise = max_rise if max_rise != -float('inf') else None
        stock_name = code_map.get(table_name, "")
        results.append((table_name, stock_name, max_rise, min_date, min_close, max_date, max_close))
    # 保存到新表
    print("[DEBUG] 写入前有效股票数量:", len(results))
    print("[DEBUG] 有效最大涨幅样例:", [r[2] for r in results if r[2] is not None][:10])
    df_out = pd.DataFrame(results, columns=[f"code", "name", f"max_rise_{N}d", f"min_{N}d_date", f"min_{N}d_close", f"max_{N}d_date", f"max_{N}d_close"])
    df_out["code"] = df_out["code"].astype(str).str.zfill(6)
    mdb.executeSql(f"DROP TABLE IF EXISTS max_rise_{N}d")
    df_out.to_sql(f"max_rise_{N}d", mdb.engine(), if_exists="replace", index=False)
    print(f"已保存到数据库表 max_rise_{N}d")


def detect_abnormal(period=10, board_type='main'):
    """
    通用异动检测函数。
    period: 10或30
    board_type: 'main'（主板）或 'gem_star'（创业/科创板）
    """
    import pandas as pd
    from datetime import datetime
    if period == 10:
        table = 'max_rise_10d'
        rise_threshold = 1
        extra_threshold = 2
    else:
        table = 'max_rise_30d'
        rise_threshold = 2
        extra_threshold = 3
    if board_type == 'main':
        prefix = ("600", "601", "603", "605", "000", "001", "002", "003")
        extra_ratio = 1.1
        board_name = '主板'
    else:
        prefix = ("300", "301", "688")
        extra_ratio = 1.2
        board_name = '创业/科创板'
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", mdb.engine())
    except Exception as e:
        print(f"读取{table}表失败: {e}")
        return
    df = df[df["code"].astype(str).str.zfill(6).str.startswith(prefix)]
    # 只保留最高价日>最低价日的记录
    max_col = f"max_{period}d_date"
    max_close_col = f"max_{period}d_close"
    min_col = f"min_{period}d_date"
    min_close_col = f"min_{period}d_close"
    rise_col = f"max_rise_{period}d"
    df = df[df[max_col] > df[min_col]].copy()
    # 调试：显示涨幅列的最大/最小值、类型、前10大涨幅股票
    print(f"[DEBUG] {table} {board_name} {period}d 涨幅列类型: {df[rise_col].dtype}")
    print(f"[DEBUG] {table} {board_name} {period}d 涨幅最大值: {df[rise_col].max()}")
    print(f"[DEBUG] {table} {board_name} {period}d 涨幅最小值: {df[rise_col].min()}")
    print(f"[DEBUG] {table} {board_name} {period}d 前10大涨幅:")
    print(df[["code", "name", rise_col, min_col, min_close_col, max_col, max_close_col]].sort_values(rise_col, ascending=False).head(10))
    # 1. 最大涨幅超过阈值
    df[rise_col] = pd.to_numeric(df[rise_col], errors='coerce')
    abnormal = df[df[rise_col] > rise_threshold]
    today = datetime.now().strftime("%Y-%m-%d")
    if not abnormal.empty:
        for _, row in abnormal.iterrows():
            print(f"[{board_name}-{period}日] 股票代码: {row['code']} | 名称: {row['name']} | {period}日最大涨幅: {row[rise_col]:.2%} | 最高价日: {row[max_col]} | 最低价日: {row[min_col]} | 当前涨幅: {row[rise_col]:.2%} | {today} 已严重异动")
    else:
        print(f"无{period}日涨幅超过{rise_threshold*100:.0f}%的{board_name}股票")
    # 2. 进一步筛选"今日收盘价*extra_ratio/最低价 > extra_threshold"
    abnormal_codes = set(abnormal["code"].astype(str).str.zfill(6))
    for _, row in df.iterrows():
        code = str(row['code']).zfill(6)
        if code in abnormal_codes:
            continue
        min_date = row[min_col]
        try:
            sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
            latest = mdb.executeSqlFetch(sql)
            if not latest or latest[0][0] is None:
                continue
            latest_close = float(latest[0][0])
            sql = f"SELECT close FROM `{code}` WHERE date = '{min_date}' AND close IS NOT NULL LIMIT 1"
            min_close = mdb.executeSqlFetch(sql)
            if not min_close or min_close[0][0] is None:
                continue
            min_close = float(min_close[0][0])
            if min_close > 0 and (latest_close * extra_ratio / min_close) > extra_threshold:
                zf2 = (min_close * 2 - latest_close) / latest_close
                print(f"[{board_name}-{period}日] 股票代码: {row['code']} | 名称: {row['name']} | 最新收盘价: {latest_close} | {period}日前最低价: {min_close} | {period}日前最低价日: {min_date} | 当前涨幅: {(latest_close / min_close - 1):.2%} | 明日涨{zf2:.2%}将严重异动")
        except Exception as e:
            print(f"处理股票{code}时异常: {e}")

def export_abnormal_tables():
    """
    整理输出10日异动榜和30日异动榜，包含：code，名称，最大涨幅，最低价日，最高价日，备注。
    """
    import pandas as pd
    from datetime import datetime
    results = []
    for period in [10, 30]:
        table = f"max_rise_{period}d"
        rise_threshold = 1 if period == 10 else 2
        # 读取表
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", mdb.engine())
        except Exception as e:
            print(f"读取{table}表失败: {e}")
            results.append(pd.DataFrame(columns=["code", "name", "最大涨幅", "最低价日", "最高价日", "备注"]))
            continue
        # 只保留最高价日>最低价日的记录
        max_col = f"max_{period}d_date"
        min_col = f"min_{period}d_date"
        rise_col = f"max_rise_{period}d"
        df = df[df[max_col] > df[min_col]].copy()
        # 异动榜
        abnormal = df[df[rise_col] > rise_threshold].copy()
        abnormal["备注"] = "已严重异动"
        # zf2相关股票
        zf2_rows = []
        for _, row in df.iterrows():
            code = str(row['code']).zfill(6)
            if code in set(abnormal["code"].astype(str).str.zfill(6)):
                continue
            min_date = row[min_col]
            max_date = row[max_col]
            if max_date <= min_date:
                continue
            try:
                sql = f"SELECT close FROM `{code}` WHERE close IS NOT NULL ORDER BY date DESC LIMIT 1"
                latest = mdb.executeSqlFetch(sql)
                if not latest or latest[0][0] is None:
                    continue
                latest_close = float(latest[0][0])
                sql = f"SELECT close FROM `{code}` WHERE date = '{min_date}' AND close IS NOT NULL LIMIT 1"
                min_close = mdb.executeSqlFetch(sql)
                if not min_close or min_close[0][0] is None:
                    continue
                min_close = float(min_close[0][0])
                # 主板和创业/科创板参数
                is_main = code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))
                is_gem_star = code.startswith(("300", "301", "688"))
                extra_ratio = 1.1 if is_main else 1.2
                extra_threshold = 2 if period == 10 else 3
                if min_close > 0 and (latest_close * extra_ratio / min_close) > extra_threshold:
                    zf2 = (min_close * 2 - latest_close) / latest_close
                    zf2_rows.append({
                        "code": code,
                        "name": row["name"],
                        "最大涨幅": latest_close / min_close - 1,
                        "最低价日": min_date,
                        "最高价日": max_date,
                        "备注": f"明日涨{zf2:.2%}将严重异动"
                    })
            except Exception as e:
                continue
        out = abnormal[["code", "name", rise_col, min_col, max_col, "备注"]].copy()
        out = out.rename(columns={rise_col: "最大涨幅", min_col: "最低价日", max_col: "最高价日"})
        if zf2_rows:
            out = pd.concat([out, pd.DataFrame(zf2_rows)], ignore_index=True)
        out["最大涨幅"] = out["最大涨幅"].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "")
        results.append(out)
    # 输出到同一张图（上下排，备注列加宽）
    out10, out30 = results
    nrows = 2
    ncols = 1
    row_num_10 = len(out10)
    row_num_30 = len(out30)
    col_num_10 = len(out10.columns)
    col_num_30 = len(out30.columns)
    base_col_width = 1.2
    remark_col_width = 4.5
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
    date = datetime(2025, 6, 10).date()
    # calc_max_rise(date, 10)
    # calc_max_rise(date, 30)
    # calc_max_rise_for_all_stocks(date, 30)
    # detect_abnormal(period=10, board_type='main')
    # detect_abnormal(period=10, board_type='gem_star')
    # detect_abnormal(period=30, board_type='main')
    detect_abnormal(period=30, board_type='gem_star')
    # export_abnormal_tables()