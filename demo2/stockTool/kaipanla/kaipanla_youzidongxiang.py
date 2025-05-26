import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlencode
from datetime import datetime

# 基础配置
BASE_URL = "https://applhb.longhuvip.com/w1/api/index.php"

HEADERS = {
    "Host": "applhb.longhuvip.com",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Sec-Fetch-Site": "same-site",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Mode": "cors",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://apppage.longhuvip.com",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148;kaipanla 5.17.0.9",
    "Referer": "https://apppage.longhuvip.com/",
}


def main():
    # 页面配置
    st.set_page_config(
        page_title="龙虎榜数据看板",
        layout="wide",
        page_icon="📊"
    )

    # 侧边栏配置
    with st.sidebar:
        st.header("🔍 查询参数设置")
        selected_date = st.date_input(
            "选择查询日期",
            value=datetime.today(),
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2025, 12, 31)
        )

    # 主界面
    st.title("🏦 龙虎榜交易数据实时看板")

    # 获取数据
    with st.spinner("🚀 正在获取最新数据..."):
        df = fetch_data(selected_date.strftime("%Y-%m-%d"))

    if df is not None:
        show_data(df)
    else:
        st.error("❌ 数据获取失败，请检查网络连接或参数设置")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data(date_str):
    """获取数据并缓存"""
    try:
        query_params = {
            "apiv": "w38",
            "PhoneOSNew": 2,
            "VerSion": "5.17.0.9"
        }

        form_data = {
            "c": "Index",
            "a": "YouZiDongXiangByList",
            "Time": date_str,  # 动态日期参数
            #"UserID": "xxxx",
            #"Token": "xxxx",
            #"DeviceID": "xxxx"
        }

        encoded_params = urlencode(query_params)
        full_url = f"{BASE_URL}?{encoded_params}"

        response = requests.post(
            full_url,
            data=form_data,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code == 200:
            return parse_longhu_data(response.json())
        return None

    except Exception as e:
        st.error(f"请求异常：{str(e)}")
        return None


def parse_longhu_data(data):
    """数据解析"""
    print(data)
    results = []
    for dongxiang in data.get("DongXiang", []):
        #print(dongxiang)
        for list_item in dongxiang.get("List", []):
            #print(list_item)
            for slist in list_item.get("Slist", []):

                #print(slist.get(0))
                # 处理买入
                if "BuyList" in slist:
                    for buy in slist.get("BuyList", []):
                        #print(buy)
                        if buy.get("AssocIcon") == 1:
                            xiwei = dongxiang.get("ShortName")
                            record = {
                                "营业部ID": buy.get("ID", ""),
                                "营业部名称": buy.get("Name", "未知营业部"),
                                "关联席位": xiwei,
                                "股票代码": str(buy.get("StockID", "")),
                                "操作类型": "买入",
                                "买入金额(万)": round(float(buy.get("Buy", 0)) / 10000, 2),
                                "卖出金额(万)": round(float(buy.get("Sell", 0)) / 10000, 2),
                                "交易日期": buy.get("Day", dongxiang.get("Time", "")),
                                "上榜原因": ", ".join(slist.get("UpReason", ["无"]))

                            }
                            results.append(record)
                if "SellList" in slist:
                    # 处理卖出
                    for sell in slist.get("SellList", []):
                        if sell.get("AssocIcon") == 1:
                            xiwei = dongxiang.get("ShortName")
                            record = {
                                "营业部ID": sell.get("ID", ""),
                                "营业部名称": sell.get("Name", "未知营业部"),
                                "关联席位": xiwei,
                                "股票代码": str(sell.get("StockID", "")),
                                "操作类型": "卖出",
                                "买入金额(万)": round(float(sell.get("Buy", 0)) / 10000, 2),
                                "卖出金额(万)": round(float(sell.get("Sell", 0)) / 10000, 2),
                                "交易日期": sell.get("Day", dongxiang.get("Time", "")),
                                "上榜原因": ", ".join(slist.get("UpReason", ["无"]))
                            }
                            results.append(record)

    df = pd.DataFrame(results)
    if not df.empty:
        df["交易日期"] = pd.to_datetime(df["交易日期"])
    return df


def show_data(df):
    """数据展示模块"""
    # 关键指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总记录数", len(df))
    with col2:
        st.metric("总买入金额(万)", round(df["买入金额(万)"].sum(), 2))
    with col3:
        st.metric("总卖出金额(万)", round(df["卖出金额(万)"].sum(), 2))

    # 主数据表
    st.subheader("📋 详细交易数据")
    st.dataframe(
        df,
        use_container_width=True,
        height=600,
        column_config={
            "交易日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "买入金额(万)": st.column_config.NumberColumn(format="¥%.2f 万"),
            "卖出金额(万)": st.column_config.NumberColumn(format="¥%.2f 万")
        }
    )

    # 分析模块
    with st.expander("📈 数据分析"):
        tab1, tab2 = st.tabs(["营业部排行", "股票分析"])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**买入TOP10**")
                top_buy = df.groupby("营业部名称")["买入金额(万)"].sum().nlargest(10)
                st.bar_chart(top_buy)
            with col2:
                st.markdown("**卖出TOP10**")
                top_sell = df.groupby("营业部名称")["卖出金额(万)"].sum().nlargest(10)
                st.bar_chart(top_sell)

        with tab2:
            selected_stock = st.selectbox("选择股票代码", df["股票代码"].unique())
            stock_df = df[df["股票代码"] == selected_stock]

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{selected_stock} 买卖统计**")
                st.dataframe(stock_df.groupby("操作类型").agg({
                    "买入金额(万)": "sum",
                    "卖出金额(万)": "sum"
                }))
            with col2:
                st.markdown("**操作记录**")
                st.dataframe(stock_df)


if __name__ == "__main__":
    main()