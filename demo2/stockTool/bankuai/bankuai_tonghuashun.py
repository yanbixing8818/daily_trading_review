import streamlit as st
import pywencai
import requests
import json
import pandas as pd

# 启用Streamlit缓存
@st.cache_data(ttl=3600)  # 缓存1小时
def get_concept_index():
    """获取概念指数数据并缓存"""
    return pywencai.get(query="同花顺概念指数", query_type="zhishu", sort_order='desc', loop=True)


def app():
    st.title("同花顺概念指数")

    # 初始化session状态
    if 'selected_code' not in st.session_state:
        st.session_state.selected_code = None

    # 第一部分：概念指数列表（使用缓存）
    with st.container():
        st.subheader("概念指数列表")
        df = get_concept_index()

        # 创建下拉选择框[1,4](@ref)
        options = list(zip(df['指数简称'], df['code']))  # 生成(显示名称, code)元组列表
        selected_code = st.selectbox(
            "选择概念指数",
            options=options,
            index=None,  # 默认不选中任何选项[3](@ref)
            format_func=lambda x: x[0],  # 显示简称[5](@ref)
            key='concept_select'
        )

        # 更新选中状态
        st.session_state.selected_code = selected_code[1] if selected_code else None
        st.write(f"总共显示 {len(df)} 个概念指数")

    # 第二部分：成分股展示（动态更新）
    if st.session_state.selected_code:
        with st.container():
            st.subheader(f"概念指数 {st.session_state.selected_code} 成分股列表")
            show_stock_list(st.session_state.selected_code)


def show_stock_list(code):
    """显示成分股的独立组件"""
    # 构造请求URL
    url = f"https://d.10jqka.com.cn/v2/blockrank/{code}/199112/d1000.js"
    headers = {
        'Referer': 'http://q.10jqka.com.cn/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }

    try:
        with st.spinner("正在加载成分股..."):
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                # 处理JSONP数据
                json_str = response.text.split('(', 1)[1].rsplit(')', 1)[0]
                data = json.loads(json_str)

                # 提取并展示数据
                stock_list = data.get('items', [])
                if stock_list:
                    stocks_df = pd.DataFrame(
                        [(s.get('5', '').zfill(6),
                          s.get('55', ''),
                          f"{float(s.get('8', 0)):.2f}",
                          f"{float(s.get('199112', 0)):.2f}%")
                         for s in stock_list],
                        columns=['股票代码', '股票名称', '最新价', '涨跌幅']
                    )
                    st.dataframe(stocks_df, use_container_width=True)
                else:
                    st.warning("未找到相关个股数据")
            else:
                st.error(f"请求失败，状态码：{response.status_code}")
    except Exception as e:
        st.error(f"获取数据时发生错误：{str(e)}")


if __name__ == "__main__":
    #st.set_page_config(page_title="同花顺概念指数分析", layout="wide")
    app()