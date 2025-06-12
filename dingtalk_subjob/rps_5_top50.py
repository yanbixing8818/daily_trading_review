from core.rps import RPS
import core.database as mdb
from datetime import datetime
import pandas as pd
from core.dingtalk.dingtalk_usage import send_to_dingtalk
import io
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database

def get_rps_5_top50():
    # 读取rps_5表，取前50名
    sql = "SELECT code, name, rps_5, rps_5_rank, today_date FROM rps_5 ORDER BY rps_5_rank DESC LIMIT 50"
    rows = mdb.executeSqlFetch(sql)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["代码", "名称", "RPS5", "RPS5归一化排名", "日期"])
    # RPS5列转为百分比字符串，保留两位小数
    df["5日涨幅"] = (df["RPS5"] * 100).round(2).astype(str) + "%"
    df = df.drop(columns=["RPS5"])  # 删除原RPS5列
    df["RPS数值"] = df["RPS5归一化排名"]
    df = df.drop(columns=["RPS5归一化排名"])  # 删除原RPS5列
    # 调整列顺序
    df = df[["代码", "名称", "5日涨幅", "RPS数值", "日期"]]
    return df

def send_rps_5_top50_to_dingtalk():
    today = datetime.now().date()
    df = get_rps_5_top50()
    if df is None or df.empty:
        print("rps_5表无数据")
        return
    # 生成表格图片
    fig, ax = plt.subplots(figsize=(10, min(20, 0.4*len(df)+1)))
    ax.axis('off')
    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(df.columns))))
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    buf.seek(0)
    send_to_dingtalk(buf, message=f"{today} RPS5前50股票榜单")
    plt.close(fig)

if __name__ == "__main__":
    send_rps_5_top50_to_dingtalk()

