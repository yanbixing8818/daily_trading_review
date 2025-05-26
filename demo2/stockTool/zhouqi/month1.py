import streamlit as st
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# 解决中文乱码问题
plt.rcParams['font.sans-serif'] = ['STHeiti']  # 苹果系统字体
#plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 设置页面标题
#st.set_page_config(page_title="上证指数1月行情分析", layout="wide")
st.title("2015-2024年1月份上证指数行情分析")

# 获取数据
@st.cache_data
def get_shanghai_index(year):
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        df_year = df[(df['date'].dt.year == year) & (df['date'].dt.month == 2)]
        return df_year.sort_values('date')
    except Exception as e:
        st.error(f"获取{year}年数据时出错: {str(e)}")
        return pd.DataFrame()

# 初始化结果表
results = []

# 分析数据（保持原有逻辑不变）
for year in range(2015, 2025):
    df = get_shanghai_index(year)
    if not df.empty:
        # 全月数据
        full_month_start = df.iloc[0]['close']
        full_month_end = df.iloc[-1]['close']
        full_month_change = (full_month_end - full_month_start) / full_month_start * 100

        # 上半月（1-15日）
        first_half = df[df['date'].dt.day <= 15]
        if not first_half.empty:
            first_half_start = first_half.iloc[0]['close']
            first_half_end = first_half.iloc[-1]['close']
            first_half_change = (first_half_end - first_half_start) / first_half_start * 100
        else:
            first_half_change = None

        # 下半月（16日之后）
        second_half = df[df['date'].dt.day > 15]
        if not second_half.empty:
            second_half_start = second_half.iloc[0]['close']
            second_half_end = second_half.iloc[-1]['close']
            second_half_change = (second_half_end - second_half_start) / second_half_start * 100
        else:
            second_half_change = None

        results.append({
            '年份': year,
            '全月涨跌幅 (%)': round(full_month_change, 2),
            '上半月涨跌幅 (%)': round(first_half_change, 2) if first_half_change else None,
            '下半月涨跌幅 (%)': round(second_half_change, 2) if second_half_change else None
        })

# 创建DataFrame
results_df = pd.DataFrame(results)

# 显示原始数据（修改颜色逻辑）
st.subheader("历史数据明细")
styled_df = results_df.style.applymap(
    lambda x: 'color: red' if isinstance(x, (int, float)) and x > 0 else 'color: green',
    subset=['全月涨跌幅 (%)', '上半月涨跌幅 (%)', '下半月涨跌幅 (%)']
)
st.dataframe(styled_df, use_container_width=True)

# 显示统计数据（保持原有逻辑不变）
st.subheader("统计分析")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("全月平均涨跌幅", f"{round(results_df['全月涨跌幅 (%)'].mean(), 2)}%")
    st.metric("全月上涨概率", f"{round(len(results_df[results_df['全月涨跌幅 (%)'] > 0])/len(results_df)*100, 2)}%")

with col2:
    st.metric("上半月平均涨跌幅", f"{round(results_df['上半月涨跌幅 (%)'].mean(), 2)}%")
    st.metric("上半月上涨概率", f"{round(len(results_df[results_df['上半月涨跌幅 (%)'] > 0])/len(results_df)*100, 2)}%")

with col3:
    st.metric("下半月平均涨跌幅", f"{round(results_df['下半月涨跌幅 (%)'].mean(), 2)}%")
    st.metric("下半月上涨概率", f"{round(len(results_df[results_df['下半月涨跌幅 (%)'] > 0])/len(results_df)*100, 2)}%")

# 绘制趋势图（已解决中文乱码）
st.subheader("年度走势可视化")
fig, ax = plt.subplots(figsize=(12, 6))
results_df.set_index('年份').plot(kind='bar', ax=ax)
plt.xticks(rotation=45)
plt.ylabel('涨跌幅 (%)')
plt.title('上证指数1月份历史涨跌幅')
st.pyplot(fig)

