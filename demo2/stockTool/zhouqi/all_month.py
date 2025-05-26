import streamlit as st
import akshare as ak
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from datetime import datetime

# 设置全局样式
plt.rcParams['font.sans-serif'] = ['STHeiti']  # 苹果系统字体
# plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows系统使用此字体
plt.rcParams['axes.unicode_minus'] = False




# 自定义双色系
dual_colors = ['#4CB050', '#FF3333']  # 绿跌红涨
cmap = mcolors.ListedColormap(dual_colors)
bounds = [-100, 0, 100]  # 严格分界
norm = mcolors.BoundaryNorm(bounds, cmap.N)


# 数据获取
@st.cache_data
def get_data():
    df = ak.stock_zh_index_daily(symbol="sh000001")
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    return df[df['year'].between(2015, 2024)].sort_values('date')


# 构建月度数据
def build_table(df):
    monthly = []
    for y in range(2015, 2025):
        row = {'年份': y}
        for m in range(1, 13):
            sub = df[(df['year'] == y) & (df['month'] == m)]
            if len(sub) >= 3:
                chg = (sub.iloc[-1]['close'] / sub.iloc[0]['close'] - 1) * 100
                row[f'{m}月'] = round(chg, 2)
        monthly.append(row)
    return pd.DataFrame(monthly).set_index('年份')


# 生成热力图
def plot_heatmap(data):
    fig, ax = plt.subplots(figsize=(16, 6))
    sns.heatmap(data,
                cmap=cmap,
                norm=norm,
                annot=True,
                fmt=".1f",
                linewidths=0.5,
                cbar=False,
                annot_kws={'color': 'white', 'weight': 'bold'})
    ax.set_xticklabels(['1月', '2月', '3月', '4月', '5月', '6月',
                        '7月', '8月', '9月', '10月', '11月', '12月'])
    ax.set_title('月度涨跌幅分布', fontsize=14)
    return fig


def app():
    st.title("上证指数历年月度分析")
    # 主程序
    df = get_data()
    monthly_df = build_table(df)

    # 显示表格
    st.subheader("数据表")
    styled_df = monthly_df.style.format('{:.1f}%', na_rep="-").applymap(color_cell)
    st.dataframe(styled_df, height=450, use_container_width=True)


def color_cell(val):
    color = '#FF3333' if val >= 0 else '#4CB050'
    return f'background-color: {color}; color: white'




if __name__ == "__main__":
    app()