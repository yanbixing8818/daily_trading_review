import streamlit as st
import home
from zhangting import zhangting_lianban
from zuigaoban import  zuigaoban_zhexian
from jingjia import jingjiafenxi
from gegu import gegu
from jishuzhibiao import dapan
from jishuzhibiao import shenqijiuzhuan
from bankuai import bankuai_tonghuashun
from bankuai import bankuai_dongfangcaifu
from  qingxu import  qingxu
from huice import  huice
from zhouqi import all_month
from kaipanla import kaipanla_ticai
from xuanxue import meiriyiji

#st.set_page_config(page_title="股票分析应用")

PAGES = {
    "主页": home,
    "涨停分析": zhangting_lianban,
    "最高板分析":zuigaoban_zhexian,
    "竞价分析": jingjiafenxi,
    "个股分析": gegu,
    "大盘分析": dapan,
    '大盘情绪': qingxu,
    '同花顺概念板块分析': bankuai_tonghuashun,
    '东方财富概念板块分析': bankuai_dongfangcaifu,
    '开盘啦概念板块分析': kaipanla_ticai,
    '回测': huice,
    '神奇九转': shenqijiuzhuan,
    '历年月度分析': all_month,
    '每日宜忌': meiriyiji
}

def main():
    st.sidebar.title("股票分析导航")
    selection = st.sidebar.radio("跳转到", list(PAGES.keys()))

    page = PAGES[selection]
    page.app()

if __name__ == "__main__":
    main()