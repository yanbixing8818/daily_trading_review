import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


def search_keyword(df, keyword):
    # Search for the keyword in the 'title' column
    matched_rows = df[df['公告标题'].str.contains(keyword, case=False)]
    return matched_rows


def app():
    st.title("股票公告搜索")

    # Date selection
    today = datetime.now().date()
    date = st.date_input("选择日期", today)
    date_str = date.strftime("%Y%m%d")

    # Keyword input
    keyword = st.text_input("输入搜索关键词")

    # Search button
    if st.button("搜索"):
        if keyword:
            try:
                # Try to import akshare
                import akshare as ak

                with st.spinner('正在获取数据...'):
                    df = ak.stock_notice_report(symbol="全部", date=date_str)

                if df.empty:
                    st.warning(f"在 {date_str} 没有找到任何公告。")
                else:
                    result = search_keyword(df, keyword)

                    if result.empty:
                        st.info(f"没有找到包含关键词 '{keyword}' 的公告。")
                    else:
                        st.success(f"找到 {len(result)} 条包含关键词 '{keyword}' 的公告。")
                        st.dataframe(result[['代码', '名称', '公告标题', '网址']])

                        # Add download button
                        csv = result[['代码', '名称', '公告标题', '网址']].to_csv(index=False)
                        st.download_button(
                            label="下载搜索结果",
                            data=csv,
                            file_name=f"search_results_{date_str}_{keyword}.csv",
                            mime="text/csv"
                        )

            except ImportError:
                st.error("无法导入 akshare 库。请确保已安装 akshare。")
            except Exception as e:
                st.error(f"发生错误: {str(e)}")
        else:
            st.warning("请输入搜索关键词。")

