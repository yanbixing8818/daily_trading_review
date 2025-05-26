import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go

# 设置页面标题和布局
#st.set_page_config(page_title="股票布林带指标分析", layout="wide")


# 定义计算布林带的函数
def calculate_bollinger_bands(data, window=20, num_std=2):
    """
    计算布林带指标
    :param data: 包含收盘价的DataFrame
    :param window: 移动平均的窗口大小
    :param num_std: 标准差的倍数
    :return: 包含布林带上中下轨的DataFrame
    """
    # 确保 '收盘' 列存在
    if '收盘' not in data.columns:
        st.error("数据中没有 '收盘' 列。请检查数据结构。")
        return None

    sma = data['收盘'].rolling(window=window).mean()
    std = data['收盘'].rolling(window=window).std()
    bollinger_up = sma + num_std * std
    bollinger_down = sma - num_std * std
    return pd.DataFrame({'bollinger_up': bollinger_up, 'bollinger_mid': sma, 'bollinger_down': bollinger_down})


# 主应用程序
def app():
    st.title("股票布林带(BOLL)指标分析")

    # 用户输入
    stock_code = st.text_input("请输入股票代码:", "002131")
    start_date = st.date_input("开始日期", pd.to_datetime("2024-10-08"))
    end_date = st.date_input("结束日期", pd.to_datetime("2025-01-08"))

    # 布林带参数
    window = st.slider("布林带窗口大小", min_value=5, max_value=50, value=20)
    num_std = st.slider("标准差倍数", min_value=1, max_value=4, value=2)

    if st.button("分析"):
        # 使用AKShare获取股票数据
        try:
            stock_data = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date.strftime("%Y%m%d"),
                                            end_date=end_date.strftime("%Y%m%d"), adjust="qfq")

            # 检查并显示列名
            #st.write("数据列名:", stock_data.columns.tolist())

            # 重命名列以确保一致性
            stock_data = stock_data.rename(columns={
                "日期": "日期",
                "开盘": "开盘",
                "收盘": "收盘",
                "最高": "最高",
                "最低": "最低",
                "成交量": "成交量"
            })
        except Exception as e:
            st.error(f"获取股票数据时出错: {e}")
            return

        # 计算布林带
        bollinger_bands = calculate_bollinger_bands(stock_data, window, num_std)

        if bollinger_bands is None:
            return

        # 合并数据
        result = pd.concat([stock_data, bollinger_bands], axis=1)

        # 创建图表
        fig = go.Figure()

        # 添加K线图
        fig.add_trace(go.Candlestick(x=result['日期'],
                                     open=result['开盘'],
                                     high=result['最高'],
                                     low=result['最低'],
                                     close=result['收盘'],
                                     increasing_line_color='red',
                                     decreasing_line_color='green',
                                     name='K线图'))

        # 添加布林带
        fig.add_trace(go.Scatter(x=result['日期'], y=result['bollinger_up'], name='上轨',
                                 line=dict(color='rgba(173, 204, 255, 0.8)')))
        fig.add_trace(go.Scatter(x=result['日期'], y=result['bollinger_mid'], name='中轨',
                                 line=dict(color='rgba(255, 191, 0, 0.8)')))
        fig.add_trace(go.Scatter(x=result['日期'], y=result['bollinger_down'], name='下轨',
                                 line=dict(color='rgba(173, 204, 255, 0.8)')))

        # 设置图表布局
        fig.update_layout(
            title=f'{stock_code} 股票价格与布林带',
            yaxis_title='价格',
            xaxis_rangeslider_visible=False,
            height=600
        )

        # 显示图表
        st.plotly_chart(fig, use_container_width=True)

        # 显示数据表格
        st.subheader("股票数据与布林带指标")
        st.dataframe(result)



if __name__ == "__main__":
    app()

