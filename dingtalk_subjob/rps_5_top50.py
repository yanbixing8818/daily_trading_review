import io
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime
from core.rps import RPS
import core.database as mdb
from core.dingtalk.dingtalk_usage import send_to_dingtalk
from core.crawling.stock_hist_baostock import get_a_hist_k_data
from core.utils import get_recent_trade_range

# 设置matplotlib中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 覆写数据库名和相关连接参数
mdb.db_database = "stock_hist"  # 替换为你想用的数据库名
mdb.MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    mdb.db_user, mdb.db_password, mdb.db_host, mdb.db_port, mdb.db_database, mdb.db_charset)
mdb.MYSQL_CONN_DBAPI['database'] = mdb.db_database

def get_rps_5_top50():
    """读取rps_5表，取前50名，返回DataFrame"""
    sql = "SELECT code, name, rps_5, rps_5_rank, today_date FROM rps_5 ORDER BY rps_5_rank DESC LIMIT 50"
    rows = mdb.executeSqlFetch(sql)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["代码", "名称", "RPS5", "RPS5归一化排名", "日期"])
    df["5日涨幅"] = (df["RPS5"] * 100).round(2).astype(str) + "%"
    df["RPS数值"] = df["RPS5归一化排名"]
    df = df.drop(columns=["RPS5归一化排名"])
    df = df[["代码", "名称", "RPS5", "5日涨幅", "RPS数值", "日期"]]
    return df

def get_baostock_code(stock_code):
    """根据股票代码查找baostock映射码"""
    sql = "SELECT baostock_mapped_code FROM cn_baostock_code_map WHERE code = '%s'" % stock_code
    rows = mdb.executeSqlFetch(sql)
    if rows and rows[0][0]:
        return rows[0][0]
    return None

def plot_history_cum_chg_for_top_stocks(df, today, n_days=30, rps5_threshold=0.4):
    """
    对于5日涨幅超过阈值的股票，画出近n_days的累计涨幅曲线，并在最后一个点标注股票名和总涨幅。
    """
    df_high = df[df["RPS5"] > rps5_threshold]
    if df_high.empty:
        print(f"无5日涨幅超过{int(rps5_threshold*100)}%的股票")
        return None
    start_date, end_date = get_recent_trade_range(today, n_days)
    fig, ax = plt.subplots(figsize=(max(10, len(df_high)*1.2), 7))
    for _, row in df_high.iterrows():
        code = row["代码"]
        name = row["名称"]
        baostock_code = get_baostock_code(code)
        if not baostock_code:
            print(f"未找到{code}的baostock映射码")
            continue
        hist_df = get_a_hist_k_data(baostock_code, start_date, end_date)
        if hist_df is None or hist_df.empty or len(hist_df) < 2:
            print(f"{code}无历史数据")
            continue
        hist_df = hist_df.sort_values("date")
        hist_df["close"] = pd.to_numeric(hist_df["close"], errors="coerce")
        hist_df = hist_df.dropna(subset=["close"]).reset_index(drop=True)
        if len(hist_df) < 2:
            continue
        # 计算累计涨幅
        start_close = hist_df["close"].iloc[0]
        hist_df["cum_chg"] = (hist_df["close"] / start_close - 1) * 100
        ax.plot(hist_df["date"], hist_df["cum_chg"], label=f"{name}({code})")
        # 在最后一个点标注股票名和总涨幅
        last_date = hist_df["date"].iloc[-1]
        last_cum_chg = hist_df["cum_chg"].iloc[-1]
        ax.text(last_date, last_cum_chg, f"{name}\n{last_cum_chg:.2f}%", ha='left', va='center', fontsize=10, fontweight='bold')
    ax.set_title(f"{today} 5日涨幅超过{int(rps5_threshold*100)}%的股票累计涨幅曲线（近{n_days}日）")
    ax.set_xlabel("日期")
    ax.set_ylabel("累计涨幅(%)")
    ax.legend(fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.5)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    buf.seek(0)
    plt.close(fig)
    return buf

def send_rps_5_top50_to_dingtalk():
    """主流程：发送RPS5前50榜单和累计涨幅曲线到钉钉"""
    today = datetime.now().date()
    df = get_rps_5_top50()
    if df is None or df.empty:
        print("rps_5表无数据")
        return
    # 发送榜单表格
    fig, ax = plt.subplots(figsize=(10, min(20, 0.4*len(df)+1)))
    ax.axis('off')
    table = ax.table(cellText=df.drop(columns=["RPS5"]).values, colLabels=df.drop(columns=["RPS5"]).columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(df.drop(columns=["RPS5"]).columns))))
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    buf.seek(0)
    send_to_dingtalk(buf, message=f"{today} RPS5前50股票榜单")
    plt.close(fig)
    # 发送累计涨幅曲线
    buf2 = plot_history_cum_chg_for_top_stocks(df, today, n_days=30, rps5_threshold=0.4)
    if buf2:
        send_to_dingtalk(buf2, message=f"{today} 5日涨幅超过40%的股票累计涨幅曲线")

if __name__ == "__main__":
    send_rps_5_top50_to_dingtalk()

