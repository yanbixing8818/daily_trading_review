import streamlit as st
from datetime import datetime, timedelta
import pywencai
import pandas as pd
import plotly.graph_objects as go
import pandas_market_calendars as mcal
from contextlib import contextmanager

@contextmanager
def st_spinner(text="处理中..."):
    try:
        with st.spinner(text):
            yield
    finally:
        pass

def app():
    # 设置页面标题
    st.title('涨停股最高板分析')

    with st_spinner("正在获取和处理数据，请稍候..."):
        # 获取当前日期并往前推20天（增加天数以便滑动）
        end_date = datetime.now()
        dates = [(end_date - timedelta(days=x)).strftime('%Y%m%d') for x in range(20)]

        # 获取中国的交易日历
        nyse = mcal.get_calendar('XSHG')
        trading_schedule = nyse.schedule(start_date=min(dates), end_date=max(dates))
        trading_days = trading_schedule.index.strftime('%Y%m%d').tolist()

        # 存储结果的列表
        results = []

        # 循环获取每个日期的数据，仅在交易日执行
        for date in trading_days:
            query = f"非ST，{date}连续涨停天数排序，涨停原因"
            try:
                data = pywencai.get(query=query)
                if not data.empty:
                    # 获取最高连续涨停天数
                    max_days = data[f'连续涨停天数[{date}]'].max()
                    # 筛选出所有最高连续涨停天数的股票
                    highest_stocks = data[data[f'连续涨停天数[{date}]'] == max_days]
                    for _, row in highest_stocks.iterrows():
                        results.append({
                            '日期': datetime.strptime(date, '%Y%m%d'),
                            '股票简称': row['股票简称'],
                            '股票代码': row['股票代码'],
                            '连续涨停天数': row[f'连续涨停天数[{date}]'],
                            '涨停原因': row[f'涨停原因类别[{date}]']
                        })
            except Exception as e:
                st.error(f"查询 {date} 数据时出错: {e}")

        # 检查是否有数据
        if results:
            # 创建一个DataFrame来存储所有数据
            df_all = pd.DataFrame(results)

            # 按日期排序
            df_filtered = df_all.sort_values('日期', ascending=True)

            # 创建一个字典来存储每个日期的股票
            date_stocks = {}
            for _, row in df_filtered.iterrows():
                date = row['日期'].strftime('%Y-%m-%d')
                if date not in date_stocks:
                    date_stocks[date] = []
                date_stocks[date].append(row['股票简称'])

            # 创建图表数据
            x = []
            y = []
            text = []
            hover_text = []

            for date, stocks in date_stocks.items():
                for i, stock in enumerate(stocks):
                    stock_data = df_filtered[(df_filtered['日期'].dt.strftime('%Y-%m-%d') == date) & (
                                df_filtered['股票简称'] == stock)].iloc[0]
                    x.append(date)
                    y.append(i)
                    text.append(f"{stock}({stock_data['连续涨停天数']}板)")

                    hover_text.append(f"{stock}({stock_data['股票代码']})<br>连续涨停天数: {stock_data['连续涨停天数']}<br>涨停原因: {stock_data['涨停原因']}")

            # 创建图表
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=x,
                y=y,
                mode='markers+text',
                marker=dict(size=10, color='red'),
                text=text,
                textposition='top center',
                hovertext=hover_text,
                hoverinfo='text'
            ))

            # 更新布局
            fig.update_layout(
                title='最高涨停股分布',
                xaxis_title='日期',
                yaxis_title='股票',
                xaxis=dict(
                    type='category',
                    tickangle=45
                ),
                yaxis=dict(
                    showticklabels=False,
                    showgrid=False
                ),
                hovermode='closest',
                showlegend=False,
                height=600,
                margin=dict(l=50, r=50, t=80, b=100),
            )

            # 全屏展示图表
            st.plotly_chart(fig, use_container_width=True)

            df_table = df_all.sort_values('日期', ascending=False)

            st.subheader("最高板股票详情")
            for date, group in df_table.groupby('日期', sort=False):
                st.write(f"日期: {date.strftime('%Y-%m-%d')}")
                st.dataframe(group[['股票简称', '股票代码', '连续涨停天数', '涨停原因']])
                st.write("---")
        else:
            st.warning("没有找到符合条件的数据")

if __name__ == "__main__":
    #st.set_page_config(layout="wide")
    app()