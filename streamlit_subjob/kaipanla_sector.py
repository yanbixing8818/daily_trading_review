# -*- coding: utf-8 -*-
import streamlit as st
import requests
import datetime
import pandas as pd
import json


def get_sector_data(date, k):
    # 基本URL
    url1 = "https://apphq.longhuvip.com/w1/api/index.php"
    url2 = "https://apphis.longhuvip.com/w1/api/index.php"

    # 请求头配置（完全匹配API要求）
    headers = {
        "Host": "apphis.longhuvip.com" if k == 1 else "apphq.longhuvip.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "User-Agent": "lhb/5.17.9 (com.kaipanla.www; build:0; iOS 16.6.0) Alamofire/4.9.1",
        "Accept-Language": "zh-Hans-CN;q=1.0",
        "Accept-Encoding": "gzip;q=1.0, compress;q=0.5"
    }

    # 构建请求体参数（完全匹配API格式）
    params = {
        "Date": date if k == 1 else datetime.date.today().strftime("%Y-%m-%d"),
        "Index": "0",
        "Order": "1",
        "PhoneOSNew": "2",
        "Type": "1",
        "VerSion": "5.17.0.9",
        "ZSType": "7",
        "a": "RealRankingInfo",
        "apiv": "w38",
        "c": "ZhiShuRanking",
        "st": "20"
    }

    url = url1 if k == 0 else url2
    print(f"请求URL: {url}")
    print(f"请求参数: {params}")

    try:
        # 发送POST请求（参数放在请求体中）
        response = requests.post(
            url,
            headers=headers,
            data=params
        )

        if response.status_code == 200:
            data = response.json()
            if "list" in data and data["list"]:
                sector_list = []
                for item in data["list"]:
                    if len(item) >= 4:
                        sector_list.append({
                            "代码": item[0],
                            "名称": item[1],
                            "强度": item[2],
                            "涨幅%": item[3]
                        })
                return sector_list
            else:
                st.error("返回数据缺少'list'字段或为空")
        else:
            st.error(f"API返回错误状态码: {response.status_code}")
    except Exception as e:
        st.error(f"获取数据时出错：{str(e)}")
    return []


def get_stock_data(sector_code, date, k):
    # 基本URL
    url1 = "https://apphq.longhuvip.com/w1/api/index.php"
    url2 = "https://apphis.longhuvip.com/w1/api/index.php"

    # 请求头配置
    headers = {
        "Host": "apphis.longhuvip.com" if k == 1 else "apphq.longhuvip.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "User-Agent": "lhb/5.17.9 (com.kaipanla.www; build:0; iOS 16.6.0) Alamofire/4.9.1",
        "Accept-Language": "zh-Hans-CN;q=1.0",
        "Accept-Encoding": "gzip;q=1.0, compress;q=0.5"
    }

    # 构建请求体参数
    params = {
        "PlateID": sector_code,
        "Date": date if k == 1 else datetime.date.today().strftime("%Y-%m-%d"),
        "Index": "0",
        "Order": "1",
        "PhoneOSNew": "2",
        "Type": "6",
        "VerSion": "5.17.0.9",
        "a": "ZhiShuStockList_W8",
        "apiv": "w38",
        "c": "ZhiShuRanking",
        "st": "20"
    }

    url = url1 if k == 0 else url2


    try:
        # 发送POST请求（参数放在请求体中）
        response = requests.post(
            url,
            headers=headers,
            data=params  # 关键修改：使用data参数
        )

        if response.status_code == 200:
            data = response.json()
            if "list" in data and data["list"]:
                stock_list = []
                for item in data["list"]:
                    if len(item) >= 24:  # 确保有足够字段
                        stock_list.append({
                            "代码": item[0],
                            "名称": item[1],
                            "涨幅%": item[6],
                            "连板": item[23],
                            "板块": item[4]
                        })
                return stock_list
            else:
                st.error("个股返回数据缺少'list'字段或为空")
    except Exception as e:
        st.error(f"获取个股数据时出错：{str(e)}")
    return []


def app():
    st.title("精选板块")

    today = datetime.date.today()
    formatted_today = today.strftime("%Y-%m-%d")
    date_range = [today - datetime.timedelta(days=i) for i in range(30)]
    formatted_date_range = [date.strftime("%Y-%m-%d") for date in date_range]
    selected_date = st.selectbox("选择日期", formatted_date_range, index=0)

    # 确定数据源类型（实时/历史）
    k = 0 if selected_date == formatted_today else 1

    # 获取板块数据
    sector_data = get_sector_data(selected_date, k)

    if sector_data:
        df = pd.DataFrame(sector_data)
        st.dataframe(df)

        # 添加个股查询功能
        selected_sector_code = st.selectbox("选择板块代码查看个股信息", df["代码"].tolist())
        if selected_sector_code:
            stock_data = get_stock_data(selected_sector_code, selected_date, k)
            if stock_data:
                stock_df = pd.DataFrame(stock_data)
                st.dataframe(stock_df)
            else:
                st.warning("未获取到个股数据，请检查参数或网络连接")
    else:
        st.error("获取板块数据失败，请稍后重试")


if __name__ == "__main__":
    app()