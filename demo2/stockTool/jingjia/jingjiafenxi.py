import streamlit as st
from datetime import datetime, timedelta
import pywencai
import time
from chinese_calendar import is_workday, is_holiday
import plotly.graph_objects as go

# Constants
MAX_STOCKS = 100
MAX_RETRIES = 1
RETRY_DELAY = 1

def safe_format(x, divisor=1, suffix=''):
    try:
        return f"{float(x)/divisor:.2f}{suffix}"
    except (ValueError, TypeError):
        return str(x)

def get_strategy_stocks(query, selected_date, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            df = pywencai.get(query=query, sort_key='竞价成交金额', sort_order='desc')
            if df is None or df.empty:
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                return None, "策略无数据"

            date_str = selected_date.strftime("%Y%m%d")
            columns_to_rename = {
                '股票代码': '股票代码',
                '股票简称': '股票简称',
                f'竞价金额[{date_str}]': '竞价金额',
                f'竞价金额排名[{date_str}]': '竞价金额排名',
                f'竞价异动类型[{date_str}]': '竞价异动类型',
                f'集合竞价评级[{date_str}]': '集合竞价评级',
                '最新涨跌幅': '涨跌幅',
                '最新价': '最新价',
                f'分时区间收盘价:前复权[{date_str} 09:25:00]': '竞价价格',
                f'竞价未匹配金额[{date_str}]': '竞价未匹配金额'
                # f'总市值[{date_str}]': '总市值'
            }
            df = df.rename(columns=columns_to_rename)
            return df[:MAX_STOCKS], None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                return None, f"Error in strategy stock selection after {max_retries} attempts: {str(e)}"

def run_strategy(query, selected_date, market_cap):
    st.write(f"选股日期: {selected_date.strftime('%Y-%m-%d')}")
    st.write(f"市值筛选: {market_cap}亿")

    if not is_workday(selected_date) or is_holiday(selected_date):
        st.warning("所选日期不是A股交易日，请选择其他日期。")
        return

    with st.spinner("正在获取股票信息..."):
        df, error = get_strategy_stocks(query, selected_date)

    if error:
        st.error(error)
        st.write("\n请检查以下内容:")
        st.write("1. 您的网络连接是否稳定。")
        st.write("2. pywencai 库是否为最新版本。")
        st.write("3. 您的查询是否有效且不太复杂。")
        st.write("4. 您是否拥有使用 pywencai 的必要权限/认证。")
        return

    if df is None or df.empty:
        st.warning("没有找到符合策略的股票。")
        return

    # Format and display the data
    df['涨跌幅'] = df['涨跌幅'].apply(lambda x: safe_format(x, suffix='%'))
    df['竞价金额'] = df['竞价金额'].apply(lambda x: safe_format(x, divisor=10000, suffix='万'))
    # df['总市值'] = df['总市值'].apply(lambda x: safe_format(x, divisor=100000000, suffix='亿'))
    df['竞价未匹配金额'] = df['竞价未匹配金额'].apply(lambda x: safe_format(x, divisor=10000, suffix='万'))


    column_order = ['股票代码', '股票简称',  '最新价', '竞价价格', '涨跌幅', '竞价金额',
                    '竞价金额排名', '竞价未匹配金额', '竞价异动类型', '集合竞价评级']
    df = df.reindex(columns=column_order)

    st.dataframe(df)

    # Create a bar chart for 竞价金额
    fig = go.Figure(data=[go.Bar(x=df['股票简称'], y=df['竞价金额'].str.replace('万', '').astype(float))])
    fig.update_layout(title='股票竞价金额对比', xaxis_title='股票', yaxis_title='竞价金额 (万元)')
    st.plotly_chart(fig)

def strategy_1(formatted_date, market_cap):
    st.session_state.current_strategy = 'strategy_1'
    query = f"""
    非ST，{formatted_date}竞价涨停，{formatted_date}竞价成交金额排序，流通市值小于{market_cap}亿
    """
    run_strategy(query, formatted_date, market_cap)

def strategy_2(formatted_date, market_cap):
    st.session_state.current_strategy = 'strategy_2'
    query = f"""
    非ST，{formatted_date}竞价跌停，{formatted_date}竞价成交金额排序，流通市值小于{market_cap}亿
    """
    run_strategy(query, formatted_date, market_cap)

def app():
    #st.set_page_config(layout="wide", page_title="竞价分析", page_icon="📈")
    st.title("竞价分析")


    col1, col2 = st.columns(2)
    with col1:
        selected_date = st.date_input("选择日期", datetime.now())
    with col2:
        market_cap_options = [100, 200, 500, 1000]
        selected_market_cap = st.selectbox("选择市值上限（亿）", market_cap_options, index=3)

    tab1, tab2 = st.tabs(["竞价涨停", "竞价跌停"])

    with tab1:
        strategy_1(selected_date, selected_market_cap)
    with tab2:
        strategy_2(selected_date, selected_market_cap)

if __name__ == "__main__":
    app()