import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

@st.cache_data(ttl=3600)
def get_industry_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取行业板块数据"""
    industry_list = ak.stock_board_industry_name_em()
    data = []

    for _, row in industry_list.iterrows():
        try:
            # 获取板块历史数据
            hist_data = ak.stock_board_industry_hist_em(
                symbol=row["板块名称"],
                start_date=start_date,
                end_date=end_date,
                adjust="hfq"
            )

            if not hist_data.empty:
                # 计算指标
                start_price = hist_data.iloc[0]['收盘']
                end_price = hist_data.iloc[-1]['收盘']
                change_pct = (end_price - start_price) / start_price * 100
                total_amount = hist_data['成交额'].sum()

                data.append({
                    "板块名称": row["板块名称"],
                    "起始价": start_price,
                    "收盘价": end_price,
                    "区间涨跌幅": change_pct,
                    "总成交额（亿）": total_amount / 1e8,
                    "日均换手率": hist_data['换手率'].mean()
                })
        except Exception as e:
            continue

    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def get_industry_stocks(board_name: str) -> pd.DataFrame:
    """获取板块成分股"""
    try:
        df = ak.stock_board_industry_cons_em(symbol=board_name)
        if not df.empty:
            # 数据清洗
            numeric_cols = ['最新价', '涨跌幅', '换手率']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            return df[['代码', '名称', '最新价', '涨跌幅', '换手率']].dropna()
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def app():





    st.title("板块与个股联动分析")
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

    st.header("显示设置")
    sort_by = st.selectbox(
        "排序指标",
        options=['区间涨跌幅', '总成交额（亿）', '日均换手率'],
        index=0
    )
    ascending = st.checkbox("升序排列")

    # 获取板块数据
    with st.spinner('正在加载板块数据...'):
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        industry_df = get_industry_data(start_str, end_str)

        if industry_df.empty:
            st.error("数据加载失败，请调整日期范围")
            return

    # 板块排行榜
    st.subheader(f"板块排行榜 ({start_date}至{end_date})")
    sorted_df = industry_df.sort_values(sort_by, ascending=ascending)


    # 交互式数据表格
    selected_board = st.dataframe(
        sorted_df,
        column_config={
            "区间涨跌幅": st.column_config.NumberColumn(
                format="▁+%.2f%%",
                help="区间涨跌幅度"
            ),
            "总成交额（亿）": st.column_config.NumberColumn(
                format="%.1f 亿",
                help="区间总成交金额"
            )
        },
        height=500,
        use_container_width=True
    )



    # ================= 个股展示 =================
    st.divider()
    st.subheader("板块成分股详情")

    # 使用session state保持选中状态
    if "selected_board" not in st.session_state:
        st.session_state.selected_board = sorted_df.iloc[0]["板块名称"]

    board_name = st.selectbox(
        "选择要分析的板块",
        options=sorted_df['板块名称'].tolist(),
        index=0,
        key="board_selector"
    )

    with st.spinner(f'正在加载 {board_name} 成分股...'):
        stocks_df = get_industry_stocks(board_name)

        if not stocks_df.empty:
            # 带颜色格式的表格
            styled_df = stocks_df.style.format({
                '涨跌幅': '{:.2f}%',
                '换手率': '{:.2f}%'
            }).applymap(
                lambda x: 'color: #e74c3c' if x > 0 else 'color: #2ecc71',
                subset=['涨跌幅']
            )

            st.dataframe(
                styled_df,
                column_config={
                    "代码": "代码",
                    "名称": "名称",
                    "最新价": st.column_config.NumberColumn(format="￥%.2f"),
                    "涨跌幅": "涨跌幅",
                    "换手率": "换手率"
                },
                height=400,
                use_container_width=True
            )
        else:
            st.warning("未能获取成分股数据，请稍后重试")




if __name__ == "__main__":
    app()