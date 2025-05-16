import streamlit as st
import pywencai
import pandas as pd
from datetime import datetime
import io
import matplotlib.pyplot as plt
import plotly.express as px

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
        # 获取数据
        param = f"{date_str}涨停，非ST"
        df = pywencai.get(query=param, sort_key='成交金额', sort_order='desc')
        if df.empty:
            st.warning("当日没有涨停股票数据！")
            return
        # 列选择和处理
        selected_columns = [
            '股票代码', '股票简称', '最新价', '最新涨跌幅',f'连续涨停天数[{date_str}]',  f'首次涨停时间[{date_str}]',
                        f'最终涨停时间[{date_str}]', f'涨停封单量[{date_str}]',
                        f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]',
                        f'几天几板[{date_str}]', f'涨停原因类别[{date_str}]',
                        f'a股市值(不含限售股)[{date_str}]'
        ]
        jj_df = df[selected_columns].copy()
        # 添加涨停原因列
        jj_df['涨停原因'] = jj_df[f'涨停原因类别[{date_str}]']
        # 调整显示列顺序（可选，将涨停原因放前面）
        display_columns = [
            '股票代码', '股票简称', '最新价', '最新涨跌幅', '涨停原因',
            f'连续涨停天数[{date_str}]', f'首次涨停时间[{date_str}]',
            f'最终涨停时间[{date_str}]', f'涨停封单量[{date_str}]',
            f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]',
            f'几天几板[{date_str}]', f'a股市值(不含限售股)[{date_str}]'
        ]
        # 展开概念列表（关键修改）
        exploded_df = jj_df.assign(
            涨停原因=lambda x: x[f'涨停原因类别[{date_str}]'].str.split('+')
        ).explode('涨停原因')
        # 正确统计出现次数（包含重复个股）
        concept_counts = exploded_df.groupby('涨停原因').size().reset_index(name='出现次数')
        concept_counts = concept_counts.sort_values('出现次数', ascending=False)
        # 显示概念统计
        # st.subheader("涨停概念统计")
        # st.dataframe(concept_counts, use_container_width=True)
        # 分组显示数据
        # st.subheader("按涨停原因分组")
        # 创建合并后的展示数据
        merged_df = pd.merge(
            exploded_df,
            concept_counts,
            on='涨停原因',
            how='left'
        ).sort_values(
            ['出现次数', '涨停原因', f'连续涨停天数[{date_str}]'],
            ascending=[False, True, False]
        )
        # 添加导出为Excel按钮
        output = io.BytesIO()
        jj_df[display_columns].to_excel(output, index=False)
        output.seek(0)
        st.download_button(
            label="导出为Excel",
            data=output,
            file_name=f"涨停分析_{date_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # 设置表格字体变大
        st.markdown(
            """
            <style>
            .big-table td, .big-table th {
                font-size: 20px !important;
            }
            .second-table td:nth-child(2) {
                min-width: 300px;
                max-width: 600px;
                word-break: break-all;
                white-space: pre-line;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        # 第一个表格
        st.table(jj_df[display_columns])
        st.divider()
        # 统计每个涨停原因对应的股票个数和股票名称列表
        reason_stock_df = jj_df[['股票简称', '涨停原因']].copy()
        reason_stock_df = reason_stock_df.assign(
            涨停原因=reason_stock_df['涨停原因'].str.split('+')
        ).explode('涨停原因')
        grouped = reason_stock_df.groupby('涨停原因').agg(
            涨停股票个数=('股票简称', 'nunique'),
            涨停股票列表=('股票简称', lambda x: '，'.join(sorted(set(x))))
        ).reset_index()
        grouped = grouped.sort_values('涨停股票个数', ascending=False)
        # 过滤掉涨停股票个数为1的原因
        grouped_heatmap = grouped[grouped['涨停股票个数'] > 1]
        # 定义渲染HTML表格的函数，确保在用到前定义
        def render_html_table(df):
            html = '<table class="big-table second-table">'
            # 表头
            html += '<tr>' + ''.join(f'<th>{col}</th>' for col in df.columns) + '</tr>'
            # 行
            for _, row in df.iterrows():
                html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
            html += '</table>'
            return html
        # 第二个表格和热力图并排显示
        col1, col2 = st.columns([2, 3])
        with col1:
            st.markdown(render_html_table(grouped.reset_index(drop=True)), unsafe_allow_html=True)
        with col2:
            fig = px.bar(
                grouped_heatmap,
                y='涨停原因',
                x='涨停股票个数',
                orientation='h',
                text='涨停股票个数',
                color='涨停股票个数',
                color_continuous_scale='Reds',
                category_orders={'涨停原因': list(grouped_heatmap['涨停原因'])}
            )
            fig.update_traces(textposition='outside')
            fig.update_layout(
                title='涨停原因热力图（Plotly）',
                xaxis_title='涨停股票个数',
                yaxis_title='涨停原因',
                height=max(400, 30 * len(grouped_heatmap)),
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"获取数据时发生错误：{str(e)}")
if __name__ == "__main__":
    st.set_page_config(page_title="涨停分析", layout="wide")
    app()