import streamlit as st
import pywencai
import pandas as pd
from datetime import datetime
import io
import matplotlib
import plotly.express as px
import plotly.graph_objects as go
import dataframe_image as dfi

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

# 列对齐设置
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_colwidth', 100)

def app():
    st.title("股票涨停分析")
    # 日期选择
    selected_date = st.date_input("选择分析日期", datetime.today())
    date_str = selected_date.strftime("%Y%m%d")
    try:
        # 先准备Excel导出用的output
        output = io.BytesIO()
        # 先定义按钮并排显示，放在最上面
        col_btn1, col_btn2 = st.columns([1,1])
        with col_btn1:
            excel_btn = st.download_button(
                label="导出为Excel",
                data=output,
                file_name=f"涨停分析_{date_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_btn2:
            save_img_btn = st.button("保存所有表格为图片")
        # 获取数据
        param = f"{date_str}涨停，非ST"
        df = pywencai.get(query=param, sort_key='成交金额', sort_order='desc')
        if df.empty:
            st.warning("当日没有涨停股票数据！")
            return
        # 列选择和处理
        selected_columns = [
            '股票代码', '股票简称', '最新价', '最新涨跌幅', f'连续涨停天数[{date_str}]', f'几天几板[{date_str}]', f'首次涨停时间[{date_str}]',
            f'最终涨停时间[{date_str}]', f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]',
            f'涨停原因类别[{date_str}]', f'a股市值(不含限售股)[{date_str}]'
        ]
        jj_df = df[selected_columns].copy()
        # 添加涨停原因列
        jj_df['涨停原因'] = jj_df[f'涨停原因类别[{date_str}]']
        display_columns = [
            '股票代码', '股票简称', '最新价', '最新涨跌幅', '涨停原因',
            f'连续涨停天数[{date_str}]', f'几天几板[{date_str}]', f'首次涨停时间[{date_str}]',
            f'最终涨停时间[{date_str}]', f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]',
            f'a股市值(不含限售股)[{date_str}]'
        ]
        # 排序和格式化
        jj_df_sorted = jj_df.sort_values(
            by=[f'首次涨停时间[{date_str}]', f'连续涨停天数[{date_str}]'],
            ascending=[True, False]
        ).reset_index(drop=True)
        jj_df_sorted['最新涨跌幅'] = pd.to_numeric(jj_df_sorted['最新涨跌幅'], errors='coerce').round(0).astype('Int64')
        # 强制去掉涨停封单量这一列
        seal_col = f'涨停封单量[{date_str}]'
        display_columns = [col for col in display_columns if col != seal_col]
        if seal_col in jj_df_sorted.columns:
            jj_df_sorted = jj_df_sorted.drop(columns=[seal_col])
        if seal_col in jj_df.columns:
            jj_df = jj_df.drop(columns=[seal_col])
        # 涨停封单额列转为万为单位，取整，不保留小数，并在数字后加"万"
        seal_amt_col = f'涨停封单额[{date_str}]'
        if seal_amt_col in jj_df_sorted.columns:
            jj_df_sorted[seal_amt_col] = pd.to_numeric(jj_df_sorted[seal_amt_col], errors='coerce').div(10000).round(0).astype('Int64').astype(str) + '万'
            jj_df[seal_amt_col] = pd.to_numeric(jj_df[seal_amt_col], errors='coerce').div(10000).round(0).astype('Int64').astype(str) + '万'
        # a股市值(不含限售股)列转为亿为单位，取整，不保留小数，并在数字后加"亿"
        old_market_col = f'a股市值(不含限售股)[{date_str}]'
        new_market_col = f'a股市值[{date_str}]'
        if old_market_col in jj_df_sorted.columns:
            jj_df_sorted[new_market_col] = pd.to_numeric(jj_df_sorted[old_market_col], errors='coerce').div(100000000).round(0).astype('Int64').astype(str) + '亿'
            jj_df[new_market_col] = pd.to_numeric(jj_df[old_market_col], errors='coerce').div(100000000).round(0).astype('Int64').astype(str) + '亿'
            jj_df_sorted = jj_df_sorted.drop(columns=[old_market_col])
            jj_df = jj_df.drop(columns=[old_market_col])
        # 更新display_columns中的列名
        display_columns = [col if col != old_market_col else new_market_col for col in display_columns]
        # 调整'几天几板'到'首次涨停时间'前面
        jtj_col = f'几天几板[{date_str}]'
        fst_col = f'首次涨停时间[{date_str}]'
        if jtj_col in display_columns and fst_col in display_columns:
            display_columns.remove(jtj_col)
            fst_idx = display_columns.index(fst_col)
            display_columns.insert(fst_idx, jtj_col)
        # 美观样式
        styler = jj_df_sorted[display_columns].style.set_table_styles(
            [
                {'selector': 'th, td', 'props': [('border', '2px solid #666'), ('padding', '6px')]},
                {'selector': 'thead th', 'props': [('background-color', '#e0e0e0'), ('color', '#222')]}
            ]
        ).set_properties(**{'border': '2px solid #666', 'padding': '6px'})
        st.markdown(f"### 股票涨停分析 {date_str}")
        st.markdown(styler.to_html(), unsafe_allow_html=True)
        st.markdown('<br>', unsafe_allow_html=True)
        # 保存Excel内容
        jj_df[display_columns].to_excel(output, index=False)
        output.seek(0)
        # 第二个表格相关
        def wrap_stock_list(stock_list):
            stocks = sorted(set(stock_list))
            lines = ['，'.join(stocks[i:i+6]) for i in range(0, len(stocks), 6)]
            return '<br>'.join(lines)
        reason_stock_df = jj_df[['股票简称', '涨停原因']].copy()
        reason_stock_df = reason_stock_df.assign(
            涨停原因=reason_stock_df['涨停原因'].str.split('+')
        ).explode('涨停原因')
        grouped = reason_stock_df.groupby('涨停原因').agg(
            个数=('股票简称', 'nunique'),
            涨停股票列表=('股票简称', wrap_stock_list)
        ).reset_index()
        grouped = grouped.sort_values('个数', ascending=False)
        # 合并个数为1的到"其他"
        grouped_gt1 = grouped[grouped['个数'] > 1].copy()
        grouped_eq1 = grouped[grouped['个数'] == 1].copy()
        if not grouped_eq1.empty:
            all_stocks = []
            for stocks in grouped_eq1['涨停股票列表']:
                all_stocks.extend(stocks.replace('<br>', '，').split('，'))
            all_stocks = sorted(set([s for s in all_stocks if s.strip()]))
            def wrap_list(stocks):
                lines = ['，'.join(stocks[i:i+6]) for i in range(0, len(stocks), 6)]
                return '<br>'.join(lines)
            other_row = {
                '涨停原因': '其他',
                '个数': len(all_stocks),
                '涨停股票列表': wrap_list(all_stocks)
            }
            grouped_final = pd.concat([grouped_gt1, pd.DataFrame([other_row])], ignore_index=True)
        else:
            grouped_final = grouped_gt1
        grouped_export = grouped_final.reset_index(drop=True)
        # 动态设置列宽
        col1_len = grouped_export['涨停原因'].map(len).max()
        col2_len = grouped_export['个数'].astype(str).map(len).max()
        col3_len = grouped_export['涨停股票列表'].map(lambda x: max([len(line) for line in x.split('<br>')])).max()
        total = col1_len + col2_len + col3_len
        col1_ratio = col1_len / total
        col2_ratio = col2_len / total
        col3_ratio = col3_len / total
        def plotly_table(df, title=""):
            fig = go.Figure(
                data=[go.Table(
                    header=dict(
                        values=list(df.columns),
                        fill_color='paleturquoise',
                        align='center',
                        font=dict(size=22, color='black', family='Microsoft YaHei,Arial'),
                        height=40
                    ),
                    cells=dict(
                        values=[df[col] for col in df.columns],
                        fill_color='lavender',
                        align=['center', 'center', 'left'],
                        font=dict(size=20, color='black', family='Microsoft YaHei,Arial'),
                        height=36
                    ),
                    columnwidth=[col1_ratio, col2_ratio, col3_ratio]
                )]
            )
            fig.update_layout(
                title=title,
                margin=dict(l=10, r=10, t=60, b=10),
                height=50 * len(df) + 120,
                width=800
            )
            return fig
        col1, col2 = st.columns([2, 3])
        with col1:
            fig_table = plotly_table(grouped_export, title="涨停原因与股票列表")
            st.plotly_chart(fig_table, use_container_width=True)
        with col2:
            grouped_heatmap = grouped_final[grouped_final['涨停原因'] != '其他']
            fig = px.bar(
                grouped_heatmap,
                y='涨停原因',
                x='个数',
                orientation='h',
                text='个数',
                color='个数',
                color_continuous_scale='Reds',
                category_orders={'涨停原因': list(grouped_heatmap['涨停原因'])}
            )
            fig.update_traces(textposition='outside')
            fig.update_layout(
                title='涨停原因热力图',
                xaxis_title='个数',
                yaxis_title='涨停原因',
                height=max(600, 40 * len(grouped_heatmap)),
                margin=dict(l=200, r=0, t=40, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)
        if save_img_btn:
            dfi.export(styler, f"涨停分析_{date_str}.png", table_conversion='matplotlib', max_rows=-1)
            fig_table.write_image(f"涨停分析_{date_str}_板块.png", width=800, height=50*len(grouped_export)+120)
            fig.write_image(f"涨停分析_{date_str}_热力图.png")
            st.success("图片已保存到本地！")
    except Exception as e:
        st.error(f"获取数据时发生错误：{str(e)}")

if __name__ == "__main__":
    st.set_page_config(page_title="涨停分析", layout="wide")
    app()