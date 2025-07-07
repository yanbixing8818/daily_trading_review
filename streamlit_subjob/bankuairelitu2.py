import streamlit as st
import akshare as ak
import plotly.express as px
import pandas as pd
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

# 自定义颜色映射
COLOR_SCALE = [
    [0.0, "#00ff00"],  # 绿色（资金流出最大）
    [0.45, "#dfffdf"], # 浅绿色（小幅流出）
    [0.5, "#ffffff"],  # 白色（平衡点）
    [0.55, "#ffe5e5"], # 浅红色（小幅流入）
    [1.0, "#ff0000"]   # 红色（资金流入最大）
]

# 数据预处理增强版
@st.cache_data(ttl=300)
def process_data(indicator):
    """强化数据预处理逻辑"""
    try:
        raw = ak.stock_sector_fund_flow_rank(
            indicator=indicator,
            sector_type="行业资金流"
        )
        raw.columns = raw.columns.str.replace(indicator, '', regex=False)
        
        # 数值转换
        df = raw.rename(columns={'名称': '板块名称'})
        
        df['资金净流入(亿)'] = df['主力净流入-净额'] / 100000000
        df['资金净流入(亿)'] = df['资金净流入(亿)'].round(2)

        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        
        # 流向强度计算
        df['流向强度'] = abs(df['资金净流入(亿)'])
        
        return df.dropna(subset=['资金净流入(亿)'])
    except Exception as e:
        st.error(f"数据错误: {str(e)}")
        return pd.DataFrame()

# 热力图生成引擎
def generate_heatmap(df):
    """生成符合金融行业标准的树状热力图"""
    fig = px.treemap(
        df,
        path=['板块名称'],
        values='流向强度',
        color='资金净流入(亿)',
        color_continuous_scale=COLOR_SCALE,
        range_color=[-max(abs(df['资金净流入(亿)'].min()), abs(df['资金净流入(亿)'].max())),
                 max(abs(df['资金净流入(亿)'].min()), abs(df['资金净流入(亿)'].max()))],
        color_continuous_midpoint=0,
        branchvalues='total',
        hover_data={
            '涨跌幅': ':%',
            '资金净流入(亿)': ':',
            '主力净流入-净占比': ':%'
        },
        height=1000
    )
    
    # 高级样式配置
    fig.update_traces(
        texttemplate=(
            "<b>%{label}</b><br>"
            "📈%{customdata[0]}%<br>"
            "💰%{customdata[1]}亿"
        ),
        hovertemplate=( 
            "<b>%{label}</b><br>"
            "涨跌幅: %{customdata[0]}%<br>"
            "资金净流入: <b>%{customdata[1]}</b>亿<br>"
            "主力占比: %{customdata[2]}%"
        ),
        textfont=dict(size=18, color='black')
    )
    
    fig.update_layout(
        margin=dict(t=0, l=0, r=0, b=0),
        coloraxis_colorbar=dict(
            title="资金流向(亿)",
            ticks="inside",
            thickness=20,
            len=0.6,
            y=0.7
        )
    )
    return fig

# 侧边栏控件组
def sidebar_controls():
    with st.sidebar:
        st.header("控制面板")
        indicator = st.radio(
            "分析周期",
            ["今日", "5日", "10日"],
            index=0,
            horizontal=True
        )
        refresh_interval = st.slider(
            "自动刷新间隔 (秒)",
            min_value=60, max_value=3600,
            value=60, step=60,
            help="设置自动刷新间隔，默认1分钟"
        )
        return indicator, refresh_interval

# 主界面
def main_display(df):
    st.title("📊 资金流向热力图")
    st.caption(f"数据更新于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not df.empty:
        with st.spinner("生成可视化..."):
            st.plotly_chart(generate_heatmap(df), use_container_width=True)
        
        # 动态摘要面板
        with st.expander("📌 实时快报", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("🔥 最强流入", 
                       f"{df['资金净流入(亿)'].max():.2f}亿",
                       df.loc[df['资金净流入(亿)'].idxmax(), '板块名称'])
            col2.metric("💧 最大流出", 
                       f"{df['资金净流入(亿)'].min():.2f}亿",
                       df.loc[df['资金净流入(亿)'].idxmin(), '板块名称'])
            col3.metric("⚖️ 多空比", 
                       f"{len(df[df['资金净流入(亿)']>0])}:{len(df[df['资金净流入(亿)']<0])}",
                       f"总净额 {df['资金净流入(亿)'].sum():.2f}亿")
    else:
        st.warning("⚠️ 数据获取失败，请检查网络连接")

# 自动刷新系统
def auto_refresh_system(refresh_interval):
    time.sleep(refresh_interval)
    st.rerun()
    print("数据刷新了")

# 主程序
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    indicator, refresh_interval = sidebar_controls()
    df = process_data(indicator)
    main_display(df)
    auto_refresh_system(refresh_interval)

