import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Function to calculate RSI
def calculate_rsi(data, periods=14):
    close_delta = data['close'].diff()

    # Make two series: one for lower closes and one for higher closes
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)

    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()

    rsi = ma_up / ma_down
    rsi = 100 - (100 / (1 + rsi))
    return rsi


# Streamlit app
st.title('股票 RSI 指标演示')

# User input
stock_code = st.text_input('输入股票代码', '300561')
rsi_period = st.slider('RSI 周期', min_value=1, max_value=30, value=14)


# Fetch data
@st.cache_data
def fetch_stock_data(stock_code):
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20241008", end_date="20250107",
                                adjust="")
        df['date'] = pd.to_datetime(df['日期'])
        df = df.rename(columns={'收盘': 'close', '开盘': 'open', '最高': 'high', '最低': 'low'})
        df = df.set_index('date')
        return df, None
    except Exception as e:
        return None, str(e)


def app():
    data, error = fetch_stock_data(stock_code)

    if error:
        st.error(f"获取股票数据时出错: {error}")
    elif data is not None and not data.empty:
        # Calculate RSI
        data['RSI'] = calculate_rsi(data, periods=rsi_period)

        # Create subplot
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=('股价', 'RSI'),
                            row_heights=[0.7, 0.3])

        # Add candlestick trace
        fig.add_trace(go.Candlestick(x=data.index,
                                     open=data['open'],
                                     high=data['high'],
                                     low=data['low'],
                                     close=data['close'],
                                     increasing_line_color='red',
                                     decreasing_line_color='green',
                                     name='股价'),
                      row=1, col=1)

        # Add RSI trace
        fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], name='RSI', line=dict(color='orange')), row=2, col=1)

        # Add RSI level lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # Update layout
        fig.update_layout(height=800, title_text=f"{stock_code} 股价和 RSI 指标")
        fig.update_xaxes(rangeslider_visible=False)
        fig.update_yaxes(title_text="股价", row=1, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1)

        # Display the plot
        st.plotly_chart(fig, use_container_width=True)

        # Display raw data
        st.subheader('原始数据')
        st.dataframe(data)
    else:
        st.error("无法获取股票数据。请检查股票代码是否正确。")

if __name__ == "__main__":
    app()