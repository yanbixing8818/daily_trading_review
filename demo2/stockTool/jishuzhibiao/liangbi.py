import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 设置页面标题
#st.set_page_config(page_title="股票 K 线图与量比分析", layout="wide")
def app():
    st.title("股票 K 线图与量比分析")

    # 输入股票代码
    stock_code = st.text_input("请输入股票代码", "002878")
    if stock_code:
        # 获取股票数据
        df = get_stock_data(stock_code)

        if df is not None and not df.empty:
            # 计算5日平均成交量
            df['5日平均成交量'] = df['成交量'].rolling(window=5).mean()

            # 计算量比
            df['量比'] = df['成交量'] / df['5日平均成交量']

            # 创建子图，正确设置 secondary_y
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                row_heights=[0.7, 0.3],
                                specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
                                subplot_titles=(f"{stock_code} K线图与成交量", "量比"))

            # 添加 K 线图
            fig.add_trace(go.Candlestick(x=df['日期'],
                                         open=df['开盘'],
                                         high=df['最高'],
                                         low=df['最低'],
                                         close=df['收盘'],
                                         increasing_line_color='red',
                                         decreasing_line_color='green',
                                         name='K线'), row=1, col=1)

            # 添加成交量柱状图作为 K 线图的子图
            fig.add_trace(go.Bar(x=df['日期'], y=df['成交量'], name='成交量',
                                 marker_color='rgba(128,128,128,0.5)'),
                          row=1, col=1, secondary_y=True)

            # 添加量比线图
            fig.add_trace(go.Scatter(x=df['日期'], y=df['量比'], mode='lines',
                                     name='量比', line=dict(color='red')),
                          row=2, col=1)

            # 更新布局
            fig.update_layout(height=800, showlegend=True,
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_xaxes(title_text="日期", row=2, col=1)
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交量", row=1, col=1, secondary_y=True)
            fig.update_yaxes(title_text="量比", row=2, col=1)

            # 设置 y 轴范围，使 K 线图和成交量在视觉上分开
            fig.update_yaxes(range=[df['最低'].min() * 0.95, df['最高'].max() * 1.05], row=1, col=1)
            fig.update_yaxes(range=[0, df['成交量'].max() * 5], row=1, col=1, secondary_y=True)

            # 显示图表
            st.plotly_chart(fig, use_container_width=True)

            # 显示数据表格
            st.subheader("数据表格")
            st.dataframe(
                df[['日期', '开盘', '收盘', '最高', '最低', '成交量', '量比']].sort_values('日期', ascending=False))


        else:
            st.warning("未能获取到股票数据，请检查股票代码是否正确。")


def get_stock_data(code):
    try:
        # 使用 akshare 获取股票数据
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20241008", end_date="20250109", adjust="")
        # 确保日期列被正确解析
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except Exception as e:
        st.error(f"获取数据时出错：{e}")
        return None




if __name__ == "__main__":
    app()

