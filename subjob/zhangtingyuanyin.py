import streamlit as st
import pywencai
import pandas as pd
from datetime import datetime
import io
import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

def save_heatmap_from_grouped(grouped, date_str):
    grouped_no_other = grouped[grouped['涨停原因'] != '其他']
    grouped_no_other = grouped_no_other.sort_values('个数', ascending=True)
    norm = plt.Normalize(grouped_no_other['个数'].min(), grouped_no_other['个数'].max())
    cmap = matplotlib.colormaps['Oranges']
    colors = [cmap(norm(v)) for v in grouped_no_other['个数']]
    fig, ax = plt.subplots(figsize=(20, max(4, 0.5 * len(grouped_no_other))))
    bars = ax.barh(grouped_no_other['涨停原因'], grouped_no_other['个数'], color=colors)
    for idx, val in enumerate(grouped_no_other['个数']):
        ax.text(val, idx, str(val), va='center', fontsize=14)
    ax.set_xlabel('个数', fontsize=14)
    ax.set_ylabel('涨停原因', fontsize=14)
    ax.set_title(f'涨停原因热力图 {date_str}', fontsize=18)
    fig.subplots_adjust(left=0.35)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    plt.close()
    buf.seek(0)
    return buf

def process_data(date_str):
    try:
        param = f"{date_str}涨停，非ST"
        df = pywencai.get(query=param, sort_key='成交金额', sort_order='desc')
        if df is None or df.empty:
            return None, None
        selected_columns = [
            '股票代码', '股票简称', '最新价', '最新涨跌幅', f'连续涨停天数[{date_str}]', f'几天几板[{date_str}]',
            f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]', f'涨停原因类别[{date_str}]', f'a股市值(不含限售股)[{date_str}]'
        ]
        jj_df = df[selected_columns].copy()
        jj_df['涨停原因'] = jj_df[f'涨停原因类别[{date_str}]']
        drop_cols = [c for c in jj_df.columns if c.startswith('涨停原因类别')]
        jj_df = jj_df.drop(columns=drop_cols, errors='ignore')
        old_market_col = f'a股市值(不含限售股)[{date_str}]'
        new_market_col = f'a股市值'
        if old_market_col in jj_df.columns:
            jj_df[new_market_col] = pd.to_numeric(jj_df[old_market_col], errors='coerce').div(100000000).round(0).astype('Int64').astype(str) + '亿'
            jj_df = jj_df.drop(columns=[old_market_col])
        seal_amt_col = f'涨停封单额[{date_str}]'
        if seal_amt_col in jj_df.columns:
            jj_df[seal_amt_col.replace(f'[{date_str}]', '')] = pd.to_numeric(jj_df[seal_amt_col], errors='coerce').div(10000).round(0).astype('Int64').astype(str) + '万'
            jj_df = jj_df.drop(columns=[seal_amt_col])
        jj_df.columns = [c.replace(f'[{date_str}]', '') for c in jj_df.columns]
        if '连续涨停天数' in jj_df.columns:
            jj_df = jj_df.sort_values(by='连续涨停天数', ascending=False).reset_index(drop=True)
        if '序号' in jj_df.columns:
            jj_df = jj_df.drop(columns=['序号'])
        jj_df.insert(0, '序号', range(1, len(jj_df) + 1))
        if '最新涨跌幅' in jj_df.columns:
            jj_df['最新涨跌幅'] = pd.to_numeric(jj_df['最新涨跌幅'], errors='coerce').fillna(0).astype(int).astype(str)
        reason_stock_df = jj_df[['股票简称', '涨停原因']].copy()
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].fillna('其他')
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].apply(lambda x: '其他' if str(x).strip() == '' else x)
        reason_stock_df = reason_stock_df.assign(
            涨停原因=reason_stock_df['涨停原因'].str.split('+')
        ).explode('涨停原因')
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].fillna('其他')
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].apply(lambda x: '其他' if str(x).strip() == '' else x)
        grouped = reason_stock_df.groupby('涨停原因').agg(
            个数=('股票简称', 'nunique'),
            涨停股票列表=('股票简称', lambda x: '，'.join(sorted(set(x))))
        ).reset_index()
        grouped = grouped.sort_values('个数', ascending=False)
        grouped_gt1 = grouped[grouped['个数'] > 1].copy()
        grouped_eq1 = grouped[grouped['个数'] == 1].copy()
        def wrap_stock_list(stock_list):
            stocks = stock_list.replace('<br>', '，').split('，')
            stocks = [s.strip() for s in stocks if s.strip()]
            lines = ['，'.join(stocks[i:i+6]) for i in range(0, len(stocks), 6)]
            return '\n'.join(lines)
        if not grouped_eq1.empty:
            all_stocks = []
            for stocks in grouped_eq1['涨停股票列表']:
                all_stocks.extend(stocks.replace('<br>', '，').split('，'))
            all_stocks = sorted(set([s for s in all_stocks if s.strip()]))
            if '其他' in grouped_gt1['涨停原因'].values:
                idx = grouped_gt1[grouped_gt1['涨停原因'] == '其他'].index[0]
                old_stocks = grouped_gt1.at[idx, '涨停股票列表']
                merged_stocks = sorted(set(old_stocks.replace('<br>', '，').split('，') + all_stocks))
                grouped_gt1.at[idx, '涨停股票列表'] = wrap_stock_list('，'.join(merged_stocks))
                grouped_gt1.at[idx, '个数'] = len(merged_stocks)
                grouped_gt1['涨停股票列表'] = grouped_gt1['涨停股票列表'].apply(wrap_stock_list)
                grouped_final = grouped_gt1.reset_index(drop=True)
            else:
                other_row = {
                    '涨停原因': '其他',
                    '个数': len(all_stocks),
                    '涨停股票列表': wrap_stock_list('，'.join(all_stocks))
                }
                grouped_gt1['涨停股票列表'] = grouped_gt1['涨停股票列表'].apply(wrap_stock_list)
                grouped_final = pd.concat([grouped_gt1, pd.DataFrame([other_row])], ignore_index=True)
        else:
            grouped_gt1['涨停股票列表'] = grouped_gt1['涨停股票列表'].apply(wrap_stock_list)
            grouped_final = grouped_gt1
        if '涨停股票列表' in grouped_final.columns and '涨停原因' in grouped_final.columns:
            mask = grouped_final['涨停原因'] == '其他'
            def wrap6(s):
                stocks = str(s).replace('\n', '，').replace('<br>', '，').split('，')
                stocks = [x for x in stocks if x.strip()]
                lines = ['，'.join(stocks[i:i+6]) for i in range(0, len(stocks), 6)]
                return '<br>'.join(lines)
            grouped_final.loc[mask, '涨停股票列表'] = grouped_final.loc[mask, '涨停股票列表'].apply(wrap6)
        return jj_df, grouped_final
    except Exception as e:
        print(f"数据处理失败: {str(e)}")
        return None, None

def app():
    date_str = datetime.now().strftime("%Y%m%d")
    jj_df_sorted, grouped = process_data(date_str)
    if jj_df_sorted is None or grouped is None:
        st.write("当日没有涨停股票数据！")
        return
    drop_cols = [c for c in jj_df_sorted.columns if c.startswith('首次涨停时间') or c.startswith('最终涨停时间') or c.startswith('涨停原因类别')]
    if drop_cols:
        jj_df_sorted = jj_df_sorted.drop(columns=drop_cols)

    st.subheader(f"涨停股票列表及板块分析")
    st.markdown(f"""
        <div class="table-title-flex">
            <span style="font-size: 1.5em; font-weight: bold;">涨停股票列表 {date_str}</span>
        </div>
        <style>
        .table-title-flex {{
            display: flex;
            justify-content: flex-start;
            width: 100%;
            margin-bottom: 0.5em;
        }}
        </style>
    """, unsafe_allow_html=True)
    st.markdown("""
        <style>
        .center-table-flex {
            display: flex;
            justify-content: center;
            align-items: flex-start;
            width: 100%;
        }
        .center-table-flex table {
            white-space: nowrap !important;
        }
        .center-table-flex th, .center-table-flex td {
            white-space: nowrap !important;
            font-size: 21px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    st.markdown(
        f'<div class="center-table-flex">{jj_df_sorted.to_html(index=False)}</div>',
        unsafe_allow_html=True
    )
    st.subheader(f"涨停原因统计 {date_str}")
    st.dataframe(grouped)
    st.subheader(f"涨停原因热力图 {date_str}")
    heatmap_buf = save_heatmap_from_grouped(grouped, date_str)
    st.image(heatmap_buf)

if __name__ == "__main__":
    app()
