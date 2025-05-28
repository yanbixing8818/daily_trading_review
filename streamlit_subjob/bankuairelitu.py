import streamlit as st
import akshare as ak
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta

@st.cache_data(ttl=3600, show_spinner=False)
def get_interval_data(start_date_str, end_date_str):
    board_df = ak.stock_board_industry_name_em()
    data_list = []

    for _, row in board_df.iterrows():
        try:
            # 获取完整区间数据
            df = ak.stock_board_industry_hist_em(
                symbol=row["板块名称"],
                start_date=start_date_str,
                end_date=end_date_str,
                adjust="qfq"
            )
            if not df.empty:
                # 计算区间涨跌幅
                start_close = df.iloc[0]['收盘']
                end_close = df.iloc[-1]['收盘']
                total_change = (end_close - start_close) / start_close * 100

                # 计算区间总成交额
                total_amount = df['成交额'].sum()

                data_list.append({
                    "板块名称": row["板块名称"],
                    "起始价": start_close,
                    "收盘价": end_close,
                    "区间涨跌幅": total_change,
                    "总成交额（亿）": total_amount / 1e8,
                    "日均换手率": df['换手率'].mean()
                })
        except Exception as e:
            continue

    return pd.DataFrame(data_list)


# 主程序
def app():
    # 侧边栏控件
    with st.sidebar:
        st.header("时间设置")
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=7),
            min_value=datetime(2020, 1, 1)
        )
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
            max_value=datetime.now()
        )

        st.header("可视化设置")
        color_scale = st.selectbox(
            "配色方案",
            options=['RdYlGn_r', 'BrBG_r', 'PiYG_r', 'RdBu_r'],
            index=0
        )
        size_metric = st.selectbox(
            "板块规模指标",
            options=['总成交额（亿）', '日均换手率'],
            index=0
        )

    # 数据加载
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    with st.spinner(f'正在获取 {start_str}-{end_str} 区间数据...'):
        df = get_interval_data(start_str, end_str)
        if df.empty:
            st.error("当前时间段无有效数据，请调整日期范围")
            return

    # 创建热力图
    fig = px.treemap(
        df,
        path=['板块名称'],
        values=size_metric,
        color='区间涨跌幅',
        color_continuous_scale=color_scale,
        range_color=[df['区间涨跌幅'].min(), df['区间涨跌幅'].max()],
        hover_data={
            '起始价': ':.2f',
            '收盘价': ':.2f',
            '区间涨跌幅': ':.2f%',
            '总成交额（亿）': ':.1f'
        },
        height=800
    )

    # 样式优化
    fig.update_layout(
        margin=dict(t=40, l=0, r=0, b=0),
        title={
            'text': f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')} 板块表现",
            'y': 0.95,
            'x': 0.5
        },
    )

    st.plotly_chart(fig, use_container_width=True)

    # 数据表格（
    with st.expander("查看详细数据排名"):
        st.dataframe(
            df.sort_values(by='区间涨跌幅', ascending=False),
            column_config={
                "板块名称": st.column_config.TextColumn(width="large"),
                "区间涨跌幅": st.column_config.NumberColumn(format="▁+%.2f%%"),
                "总成交额（亿）": st.column_config.NumberColumn(format="%.1f 亿"),
                "日均换手率": st.column_config.NumberColumn(format="%.2f%%")
            },
            height=400,
            hide_index=True
        )


if __name__ == "__main__":
    app()