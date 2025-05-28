import streamlit as st
import home
import streamlit_subjob.zhangtingyuanyin as ztyy
import streamlit_subjob.lianbantianti as lbtt
import streamlit_subjob.longtouguzongkuo as ltgzk
import streamlit_subjob.zhangdietingshuliang as zdtsl
import streamlit_subjob.all_a_stock_data as aasd
import streamlit_subjob.bankuairelitu as bkrlt

PAGES = {
    "主页": home,
    "A股市场数据": aasd,
    "龙头股总括": ltgzk,
    "涨停原因": ztyy,
    "最高板分析": lbtt,
    "涨跌停数量分析": zdtsl,
    "7日板块涨跌幅": bkrlt,
    # "竞价分析": jingjiafenxi,
    # "个股分析": gegu,
    # "大盘分析": dapan,
    # '大盘情绪': qingxu,
    # '同花顺概念板块分析': bankuai_tonghuashun,
    # '东方财富概念板块分析': bankuai_dongfangcaifu,
    # '开盘啦概念板块分析': kaipanla_ticai,
    # '回测': huice,
    # '神奇九转': shenqijiuzhuan,
    # '历年月度分析': all_month,
    # '每日宜忌': meiriyiji
}

def main():
    st.sidebar.title("每日复盘导航")
    selection = st.sidebar.radio("跳转到", list(PAGES.keys()))

    page = PAGES[selection]
    page.app()

if __name__ == "__main__":
    main()