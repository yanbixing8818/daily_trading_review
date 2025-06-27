import pandas as pd
import pywencai
from datetime import date
from core.database import insert_db_from_df, executeSqlFetch
from core.tablestructure import table_high_250d, table_high_120d, get_field_types
from sqlalchemy import DATE, VARCHAR, Integer
import matplotlib.pyplot as plt
import io
from core.dingtalk.dingtalk_usage import send_to_dingtalk
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False


def fetch_and_save_wencai_to_db(query, table_struct):
    """查询问财，按行业分组统计数量和股票列表，并保存到数据库"""
    result = pywencai.get(query=query, sort_key='成交金额', sort_order='desc')
    if result is None or len(result) == 0:
        print(f"未获取到数据：{query}")
        return
    df = pd.DataFrame(result)
    if '行业简称' not in df.columns or '股票简称' not in df.columns:
        print(f"缺少必要字段，实际字段为：{df.columns}")
        return
    grouped = df.groupby('行业简称')['股票简称'].agg(['count', lambda x: '，'.join(x)]).reset_index()
    grouped.columns = ['industry', 'stock_count', 'stock_list']
    grouped['date'] = date.today().isoformat()
    grouped = grouped[['date', 'industry', 'stock_count', 'stock_list']]
    cols_type = get_field_types(table_struct['columns'])
    insert_db_from_df(
        data=grouped,
        table_name=table_struct['name'],
        cols_type=cols_type,
        write_index=False,
        primary_keys='date,industry'
    )
    print(f"已保存到表 {table_struct['name']}")

def summarize_high_table(table_name):
    # 读取原始表
    sql = f"SELECT date, industry, stock_count FROM {table_name} ORDER BY date DESC, stock_count DESC"
    rows = executeSqlFetch(sql)
    if not rows:
        print(f"{table_name} 无数据")
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=['date', 'industry', 'stock_count'])
    # 分组聚合
    result = []
    for dt, group in df.groupby('date'):
        group = group.sort_values('stock_count', ascending=False)
        total = group['stock_count'].sum()
        max_row = group.iloc[0]
        max_industry = max_row['industry']
        max_count = max_row['stock_count']
        # 其他板块情况，最大板块放最前
        other_industries = [f"{row['industry']}{row['stock_count']}" for _, row in group.iterrows()]
        other_str = '，'.join(other_industries)
        result.append({
            '日期': dt,
            '历史新高个数': total,
            '最大板块': max_industry,
            '最大板块个数': max_count,
            '其他板块情况': other_str
        })
    return pd.DataFrame(result)

def save_summary_to_db(df, table_name):
    if df.empty:
        print(f"{table_name} 没有需要保存的数据")
        return
    # 构造字段类型
    cols_type = {
        '日期': DATE,
        '历史新高个数': Integer,
        '最大板块': VARCHAR(64),
        '最大板块个数': Integer,
        '其他板块情况': VARCHAR(1024)
    }
    # 列重命名为英文，便于数据库兼容
    df = df.rename(columns={
        '日期': 'date',
        '历史新高个数': 'total_count',
        '最大板块': 'max_industry',
        '最大板块个数': 'max_count',
        '其他板块情况': 'other_industries'
    })
    insert_db_from_df(
        data=df,
        table_name=table_name,
        cols_type=cols_type,
        write_index=False,
        primary_keys='date'
    )
    print(f"已保存到表 {table_name}")

def read_high_tables_and_summarize():
    print('--- 250日新高行业统计汇总 ---')
    df_250 = summarize_high_table('high_250d_stocks')
    print(df_250)
    print('\n--- 120日新高行业统计汇总 ---')
    df_120 = summarize_high_table('high_120d_stocks')
    print(df_120)
    # 保存到数据库
    save_summary_to_db(df_250, 'high_250d_total')
    save_summary_to_db(df_120, 'high_120d_total')
    return df_250, df_120

def fetch_total_table_as_df(table_name, n=7):
    sql = f"SELECT date, total_count, max_industry, max_count, other_industries FROM {table_name} ORDER BY date DESC LIMIT {n}"
    rows = executeSqlFetch(sql)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=['日期', '历史新高个数', '最大板块', '最大板块个数', '其他板块情况'])

def df_to_image(df, title=""):
    fig, ax = plt.subplots(figsize=(12, 2 + 0.5 * len(df)))
    ax.axis('off')
    tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.scale(1, 1.5)
    # 自动调整列宽
    tbl.auto_set_column_width(col=list(range(len(df.columns))))
    plt.title(title, fontsize=16)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf

def send_summary_images_to_dingtalk():
    df_250 = fetch_total_table_as_df('high_250d_total', 7)
    df_120 = fetch_total_table_as_df('high_120d_total', 7)
    if not df_250.empty:
        img_250 = df_to_image(df_250, title='250日新高行业统计（近7日）')
        send_to_dingtalk(img_250, message='250日新高行业统计（近7日）')
    if not df_120.empty:
        img_120 = df_to_image(df_120, title='120日新高行业统计（近7日）')
        send_to_dingtalk(img_120, message='120日新高行业统计（近7日）')

def send_lishixingao_to_dingtalk():
    fetch_and_save_wencai_to_db(
        query="今日收盘价创250日新高股票，按照同花顺行业排序",
        table_struct=table_high_250d
    )
    fetch_and_save_wencai_to_db(
        query="今日收盘价创120日新高股票，按照同花顺行业排序",
        table_struct=table_high_120d
    )
    # 读取并显示两个表的数据
    read_high_tables_and_summarize()
    send_summary_images_to_dingtalk()

if __name__ == "__main__":
    send_lishixingao_to_dingtalk()
