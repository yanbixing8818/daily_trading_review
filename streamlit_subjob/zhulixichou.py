import streamlit as st
import pandas as pd
from datetime import datetime, date
import sys
import os

# 添加项目根目录和 tdx_stock_selection 目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
tdx_selection_dir = os.path.join(project_root, 'tdx_stock_selection')

if project_root not in sys.path:
    sys.path.insert(0, project_root)
if tdx_selection_dir not in sys.path:
    sys.path.insert(0, tdx_selection_dir)

try:
    from tdx_stock_selection.zhulixichou import (
        calculate_all_stocks_main_accumulation,
        get_all_stock_codes,
        get_stock_name_map
    )
except ImportError:
    # 如果上面的导入失败，尝试直接导入
    try:
        from zhulixichou import (
            calculate_all_stocks_main_accumulation,
            get_all_stock_codes,
            get_stock_name_map
        )
    except ImportError as e:
        st.error(f"导入失败: {e}")
        st.stop()

# 默认通达信数据路径
DEFAULT_TDX_PATH = "E:/new_tdx"

@st.cache_data(ttl=3600, show_spinner=True)
def get_main_accumulation_data(tdx_data_path, target_date, max_stocks=None):
    """
    获取主力吸货数据（带缓存）
    """
    try:
        result_df = calculate_all_stocks_main_accumulation(
            tdx_data_path=tdx_data_path,
            target_date=target_date,
            max_stocks=max_stocks
        )
        return result_df
    except Exception as e:
        st.error(f"计算主力吸货数据失败: {str(e)}")
        return pd.DataFrame()

def format_dataframe_for_display(df):
    """
    格式化DataFrame以便在Streamlit中显示
    """
    if df.empty:
        return df
    
    # 确保数值列格式正确
    display_df = df.copy()
    
    # 格式化数值列
    if '收盘价' in display_df.columns:
        display_df['收盘价'] = display_df['收盘价'].apply(lambda x: f"{x:.2f}")
    if '主力吸货' in display_df.columns:
        display_df['主力吸货'] = display_df['主力吸货'].apply(lambda x: f"{x:.2f}")
    if '涨跌' in display_df.columns:
        display_df['涨跌'] = display_df['涨跌'].apply(lambda x: f"{x:.2f}")
    
    return display_df

def app():
    st.title("主力吸货排名")
    st.markdown("---")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("配置参数")
        
        # 通达信数据路径
        tdx_data_path = st.text_input(
            "通达信数据路径",
            value=DEFAULT_TDX_PATH,
            help="通达信本地数据目录路径，如 E:/new_tdx"
        )
        
        # 目标日期选择
        today = date.today()
        target_date = st.date_input(
            "目标日期",
            value=today,
            max_value=today,
            help="选择要查询的日期，默认为今天"
        )
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        # 最大股票数量限制（用于测试）
        max_stocks = st.number_input(
            "最大计算数量（测试用）",
            min_value=None,
            max_value=None,
            value=None,
            step=100,
            help="限制计算的股票数量，None表示计算全部（用于测试时可以减少计算时间）"
        )
        if max_stocks is not None and max_stocks <= 0:
            max_stocks = None
        
        # 显示数量选择
        display_count = st.number_input(
            "显示前N名",
            min_value=10,
            max_value=500,
            value=50,
            step=10,
            help="在表格中显示前N名股票"
        )
        
        st.markdown("---")
        st.info(f"当前配置：\n- 数据路径: {tdx_data_path}\n- 目标日期: {target_date_str}\n- 显示数量: {display_count}")
    
    # 检查路径是否存在
    if not os.path.exists(tdx_data_path):
        st.error(f"❌ 通达信数据路径不存在: {tdx_data_path}")
        st.info("请检查路径是否正确，或修改侧边栏中的路径配置")
        return
    
    # 计算按钮
    if st.button("开始计算", type="primary", use_container_width=True):
        with st.spinner(f"正在计算主力吸货数据（目标日期: {target_date_str}）..."):
            try:
                # 计算主力吸货数据
                result_df = get_main_accumulation_data(
                    tdx_data_path=tdx_data_path,
                    target_date=target_date_str,
                    max_stocks=max_stocks
                )
                
                if result_df.empty:
                    st.warning("⚠️ 未计算出任何结果，请检查数据路径和日期是否正确")
                    return
                
                # 保存到session state
                st.session_state['zhulixichou_result'] = result_df
                st.session_state['zhulixichou_date'] = target_date_str
                
                st.success(f"✅ 计算完成！共计算出 {len(result_df)} 只股票的数据")
                
            except Exception as e:
                st.error(f"❌ 计算过程中出错: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                return
    
    # 显示结果
    if 'zhulixichou_result' in st.session_state:
        result_df = st.session_state['zhulixichou_result']
        result_date = st.session_state.get('zhulixichou_date', target_date_str)
        
        st.markdown("---")
        st.subheader(f"主力吸货排名（日期: {result_date}）")
        
        # 显示统计信息
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总股票数", len(result_df))
        with col2:
            if not result_df.empty and '主力吸货' in result_df.columns:
                st.metric("最高主力吸货", f"{result_df['主力吸货'].max():.2f}")
        with col3:
            if not result_df.empty and '主力吸货' in result_df.columns:
                st.metric("平均主力吸货", f"{result_df['主力吸货'].mean():.2f}")
        with col4:
            if not result_df.empty and '主力吸货' in result_df.columns:
                st.metric("最低主力吸货", f"{result_df['主力吸货'].min():.2f}")
        
        # 显示前N名
        display_df = result_df.head(display_count).copy()
        display_df = format_dataframe_for_display(display_df)
        
        # 使用st.dataframe显示表格，支持排序和搜索
        st.dataframe(
            display_df,
            use_container_width=True,
            height=600,
            hide_index=True
        )
        
        # 下载按钮
        csv = result_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下载完整数据（CSV）",
            data=csv,
            file_name=f"主力吸货排名_{result_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # 显示完整数据统计
        with st.expander("📊 查看完整数据统计"):
            st.dataframe(result_df.describe(), use_container_width=True)
        
        # 风险分布
        if '风险' in result_df.columns:
            with st.expander("📈 风险值分布"):
                risk_counts = result_df['风险'].value_counts().sort_index()
                st.bar_chart(risk_counts)
    else:
        st.info("👆 请点击上方「开始计算」按钮开始计算主力吸货数据")

if __name__ == "__main__":
    app()

