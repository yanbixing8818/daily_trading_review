import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
from tdx_bankuaifenxi import check_plate_buy_point1, check_plate_buy_point2, check_plate_buy_point3
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from mootdx.reader import Reader
import collections.abc

st.set_page_config(layout="wide")

def is_invalid_date(val):
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    if isinstance(val, str):
        if val.strip() == '' or val.lower() in ['nan', 'nat', 'none']:
            return True
    try:
        ts = pd.to_datetime(val)
        if pd.isna(ts):
            return True
    except Exception:
        return True
    return False

# 初始化K线数据读取器（只初始化一次）
@st.cache_resource
def init_reader():
    return Reader.factory(market='std', tdxdir='/mnt/c/new_tdx')  # 修改为您的通达信数据目录

def load_plate_rps_history():
    path = os.path.join(os.path.dirname(__file__), 'plate_rps_history.csv')
    if not os.path.exists(path):
        st.error('plate_rps_history.csv 文件不存在，请先运行主分析脚本生成数据。')
        return None
    df = pd.read_csv(path, dtype={'code': str})
    return df

def get_buy_points(df, check_func):
    results = []
    for code, group in df.groupby('code'):
        group = group.sort_values('date')
        pre_rps5 = pre_rps10 = pre_rps20 = pre_rps60 = pre_volume = None
        for _, row in group.iterrows():
            rps5 = row['rps5']
            rps10 = row['rps10']
            rps20 = row['rps20']
            rps60 = row['rps60']
            volume = row.get('volume', None)
            volume_5d_avg = row.get('volume_5d_avg', None)
            if check_func(rps5, pre_rps5, rps10, pre_rps10, rps20, pre_rps20, 
                          rps60, pre_rps60, volume, pre_volume, volume_5d_avg):
                results.append({
                    'date': row['date'],
                    'name': row['name'],
                    'code': row['code'],
                })
            pre_rps5 = rps5
            pre_rps10 = rps10
            pre_rps20 = rps20
            pre_rps60 = rps60
            pre_volume = volume
    df_result = pd.DataFrame(results)
    if not df_result.empty:
        df_result = df_result.sort_values('date', ascending=False)
    return df_result

def plot_kline(reader, code, name, date, days=30):
    """绘制K线图"""
    try:
        dt_conv = pd.to_datetime(date, errors='coerce')
    except Exception as e:
        st.write(f"[DEBUG] plot_kline: pd.to_datetime error: {e}")
    if is_invalid_date(date):
        st.warning(f"{name}({code}) 买点日期为空，无法绘制K线图")
        return
    try:
        # 获取日线数据
        df = reader.daily(symbol=code)
        df = df.copy()
        if 'date' not in df.columns:
            df['date'] = df.index
        df['date'] = pd.to_datetime(df['date'])
        # 处理传入的date参数
        if isinstance(date, int):
            date = str(date)
        if isinstance(date, str):
            if '-' in date:
                target_date = pd.to_datetime(date)
            else:
                target_date = pd.to_datetime(date, format='%Y%m%d')
        else:
            target_date = pd.to_datetime(date)
        start_date = target_date - pd.Timedelta(days=days)
        end_date = target_date + pd.Timedelta(days=days)
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        df = df.loc[mask]
        if df.empty:
            st.warning(f"未找到 {name}({code}) 在 {target_date.strftime('%Y-%m-%d')} 附近的数据")
            return
        # 采样x轴日期，tickvals只显示约8个
        dates = df['date'].dt.strftime('%Y-%m-%d').tolist()
        N = max(1, len(dates) // 8)
        tickvals = [dates[i] for i in range(0, len(dates), N)]
        target_date_str = target_date.strftime('%Y-%m-%d')
        # 创建K线图
        fig = go.Figure(data=[go.Candlestick(
            x=dates,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            increasing_line_color='red',
            decreasing_line_color='green',
            name='K线'
        )])
        # 标记买点日期
        fig.add_vline(x=target_date_str, line_width=2, line_dash="dash", line_color="blue")
        fig.add_annotation(x=target_date_str, y=df['low'].min(), 
                          text="买点", showarrow=True, arrowhead=1)
        fig.update_layout(
            title=f"{name}({code}) K线图 - {target_date_str}",
            xaxis_title='日期',
            yaxis_title='价格',
            xaxis_rangeslider_visible=False,
            height=500,
            xaxis=dict(
                type="category",
                tickvals=tickvals,
                tickformat="%Y-%m-%d",
                tickangle=0
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"绘制K线图时出错: {str(e)}")

def main():
    st.title('TDX板块买点信号')
    reader = init_reader()
    
    df = load_plate_rps_history()
    if df is None:
        return
    
    # 初始化session state
    if "aggr_selected" not in st.session_state:
        st.session_state.aggr_selected = []
    if "sure_selected" not in st.session_state:
        st.session_state.sure_selected = []
    
    # 激进买点表格
    st.header('激进性买点')
    aggr_df = get_buy_points(df, check_plate_buy_point1)

    if not aggr_df.empty:
        aggr_df = aggr_df.head(25)  # 只显示前30行
        col1, col2 = st.columns([4, 3])  # 左宽右窄
        with col1:
            # 配置AgGrid
            gb = GridOptionsBuilder.from_dataframe(aggr_df)
            gb.configure_selection(selection_mode="single", use_checkbox=False)  # 只需点击行即可选中
            gb.configure_grid_options(domLayout='autoHeight')
            grid_options = gb.build()
            # 显示表格并获取选择
            grid = AgGrid(
                aggr_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                key='aggr_grid'
            )
            st.session_state.aggr_selected = grid['selected_rows']
        with col2:
            if st.session_state.aggr_selected is not None:
                sel = st.session_state.aggr_selected
                if isinstance(sel, pd.DataFrame):
                    if not sel.empty:
                        selected = sel.iloc[0].to_dict()
                        st.subheader(f"选中: {selected['name']} ({selected['code']}) - {selected['date']}")
                        if is_invalid_date(selected['date']):
                            st.warning(f"{selected['name']}（{selected['code']}）买点日期为空，无法绘制K线图")
                        else:
                            plot_kline(reader, selected['code'], selected['name'], selected['date'])
                elif isinstance(sel, collections.abc.Sequence) and len(sel) > 0 and isinstance(sel[0], dict):
                    selected = sel[0]
                    st.subheader(f"选中: {selected['name']} ({selected['code']}) - {selected['date']}")
                    if is_invalid_date(selected['date']):
                        st.warning(f"{selected['name']}（{selected['code']}）买点日期为空，无法绘制K线图")
                    else:
                        plot_kline(reader, selected['code'], selected['name'], selected['date'])
    else:
        st.info("当前无激进买点信号")
    
    # 确定买点表格
    st.header('确定性买点')
    sure_df = get_buy_points(df, check_plate_buy_point2)
    
    if not sure_df.empty:
        col1, col2 = st.columns([4, 3])  # 左宽右窄
        with col1:
            # 配置AgGrid
            gb = GridOptionsBuilder.from_dataframe(sure_df)
            gb.configure_selection(selection_mode="single", use_checkbox=False)  # 只需点击行即可选中
            gb.configure_grid_options(domLayout='autoHeight')
            grid_options = gb.build()
            # 显示表格并获取选择
            grid = AgGrid(
                sure_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                key='sure_grid'
            )
            st.session_state.sure_selected = grid['selected_rows']
        with col2:
            if st.session_state.sure_selected is not None:
                sel = st.session_state.sure_selected
                if isinstance(sel, pd.DataFrame):
                    if not sel.empty:
                        selected = sel.iloc[0].to_dict()
                        st.subheader(f"选中: {selected['name']} ({selected['code']}) - {selected['date']}")
                        if is_invalid_date(selected['date']):
                            st.warning(f"{selected['name']}（{selected['code']}）买点日期为空，无法绘制K线图")
                        else:
                            plot_kline(reader, selected['code'], selected['name'], selected['date'])
                elif isinstance(sel, collections.abc.Sequence) and len(sel) > 0 and isinstance(sel[0], dict):
                    selected = sel[0]
                    st.subheader(f"选中: {selected['name']} ({selected['code']}) - {selected['date']}")
                    if is_invalid_date(selected['date']):
                        st.warning(f"{selected['name']}（{selected['code']}）买点日期为空，无法绘制K线图")
                    else:
                        plot_kline(reader, selected['code'], selected['name'], selected['date'])
    else:
        st.info("当前无确定买点信号")

    # 浅回调买点表格
    st.header('浅回调买点')
    shallow_df = get_buy_points(df, check_plate_buy_point3)
    if not shallow_df.empty:
        col1, col2 = st.columns([4, 3])
        with col1:
            gb = GridOptionsBuilder.from_dataframe(shallow_df)
            gb.configure_selection(selection_mode="single", use_checkbox=False)
            gb.configure_grid_options(domLayout='autoHeight')
            grid_options = gb.build()
            grid = AgGrid(
                shallow_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                key='shallow_grid'
            )
            st.session_state['shallow_selected'] = grid['selected_rows']
        with col2:
            sel = st.session_state.get('shallow_selected', None)
            if sel is not None:
                if isinstance(sel, pd.DataFrame):
                    if not sel.empty:
                        selected = sel.iloc[0].to_dict()
                        st.subheader(f"选中: {selected['name']} ({selected['code']}) - {selected['date']}")
                        if is_invalid_date(selected['date']):
                            st.warning(f"{selected['name']}（{selected['code']}）买点日期为空，无法绘制K线图")
                        else:
                            plot_kline(reader, selected['code'], selected['name'], selected['date'])
                elif isinstance(sel, collections.abc.Sequence) and len(sel) > 0 and isinstance(sel[0], dict):
                    selected = sel[0]
                    st.subheader(f"选中: {selected['name']} ({selected['code']}) - {selected['date']}")
                    if is_invalid_date(selected['date']):
                        st.warning(f"{selected['name']}（{selected['code']}）买点日期为空，无法绘制K线图")
                    else:
                        plot_kline(reader, selected['code'], selected['name'], selected['date'])
    else:
        st.info("当前无浅回调买点信号")

if __name__ == '__main__':
    main()