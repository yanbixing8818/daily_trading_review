import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import plotly.graph_objects as go


# 获取股票数据
def get_stock_data(stock_code, start_date, end_date):
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")
    stock_zh_a_hist_df = ak.stock_zh_a_hist(
        symbol=stock_code,
        period="daily",
        start_date=start_date_str,
        end_date=end_date_str,
        adjust="qfq"
    )
    return stock_zh_a_hist_df


# 数据预处理
def preprocess_data(data):
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data[['收盘']].values)
    return scaled_data, scaler


# 创建训练数据
def create_dataset(dataset, time_step=1):
    dataX, dataY = [], []
    for i in range(len(dataset) - time_step - 1):
        a = dataset[i:(i + time_step), 0]
        dataX.append(a)
        dataY.append(dataset[i + time_step, 0])
    return np.array(dataX), np.array(dataY)


# 构建LSTM模型
def build_lstm_model(input_shape):
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=input_shape))
    model.add(LSTM(50, return_sequences=False))
    model.add(Dense(25))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model


# Streamlit应用
def app():
    st.title('股票涨跌预测系统')
    stock_code = st.text_input('请输入股票代码（例如：000001）:', '000001')

    # 调整日期输入顺序并添加验证
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input('选择开始日期', pd.Timestamp.today().date() - pd.Timedelta(days=365))
    with col2:
        end_date = st.date_input('选择结束日期', pd.Timestamp.today().date())

    if start_date > end_date:
        st.error("错误：结束日期不能早于开始日期！")
        return

    if st.button('开始预测'):
        # 获取数据
        stock_data = get_stock_data(stock_code, start_date, end_date)

        if stock_data.empty:
            st.error("未获取到数据，请检查股票代码和日期范围！")
            return

        # 数据预处理
        scaled_data, scaler = preprocess_data(stock_data)
        time_step = 60

        # 确保有足够的数据进行预测
        if len(scaled_data) < time_step:
            st.error(f"数据量不足，至少需要{time_step}个交易日的数据！")
            return

        # 创建数据集
        X_train, y_train = create_dataset(scaled_data, time_step)
        if len(X_train) == 0:
            st.error("数据量不足创建训练集，请选择更长的日期范围！")
            return

        X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)

        # 构建并训练模型
        model = build_lstm_model((X_train.shape[1], 1))
        model.fit(X_train, y_train, epochs=1, batch_size=1, verbose=2)

        # 获取最近收盘价
        latest_close = stock_data['收盘'].iloc[-1]

        # 进行预测
        test_data = scaled_data[-time_step:]
        test_data = test_data.reshape((1, time_step, 1))
        predicted_stock_price = model.predict(test_data)
        predicted_close = scaler.inverse_transform(predicted_stock_price)[0][0]

        # 计算涨跌
        change = predicted_close - latest_close
        change_percent = (change / latest_close) * 100

        # 显示结果
        st.subheader("预测结果")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("最近收盘价", f"{latest_close:.2f}")
        with col_b:
            display_text = f"{predicted_close:.2f}"
            delta_sign = ""
            if change != 0:
                delta_sign = "↑" if change > 0 else "↓"

            st.metric(
                label="预测收盘价",
                value=f"{predicted_close:.2f}",
                delta=f"{delta_sign}{abs(change):.2f} ({abs(change_percent):.2f}%)"
            )

        # 可视化图表
        fig = go.Figure()

        # 添加历史数据
        fig.add_trace(
            go.Scatter(
                x=stock_data['日期'],
                y=stock_data['收盘'],
                name='历史收盘价',
                line=dict(color='#1f77b4', width=2),
                hovertemplate='日期: %{x}<br>收盘价: %{y:.2f}'
            )
        )

        # 添加预测点
        last_date = pd.to_datetime(stock_data['日期'].iloc[-1])
        next_date = last_date + pd.Timedelta(days=1)
        pred_color = 'green' if predicted_close >= latest_close else 'red'
        symbol_icon = 'triangle-up' if predicted_close >= latest_close else 'triangle-down'

        fig.add_trace(
            go.Scatter(
                x=[next_date],
                y=[predicted_close],
                name='预测收盘价',
                mode='markers',
                marker=dict(
                    color=pred_color,
                    size=12,
                    symbol=symbol_icon,
                    line=dict(width=2, color='white')
                ),
                hovertemplate=f'预测日期: {next_date.strftime("%Y-%m-%d")}<br>预测价格: {predicted_close:.2f}'
            )
        )

        # 更新布局
        fig.update_layout(
            title=dict(
                text=f'{stock_code} 股票价格走势预测',
                x=0.05,
                xanchor='left',
                font=dict(size=20)
            ),
            xaxis=dict(
                title='日期',
                rangeslider=dict(visible=True),
                type='date'
            ),
            yaxis=dict(
                title='收盘价 (元)',
                tickprefix='¥'
            ),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=50, r=30, t=80, b=50),
            plot_bgcolor='rgba(240,240,240,0.9)',
            height=500
        )

        # 添加涨跌注释
        fig.add_annotation(
            x=next_date,
            y=predicted_close,
            text=f'{change_percent:.2f}%',
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-40,
            font=dict(
                color=pred_color,
                size=14
            )
        )

        st.plotly_chart(fig, use_container_width=True)

if __name__ == '__main__':
    app()