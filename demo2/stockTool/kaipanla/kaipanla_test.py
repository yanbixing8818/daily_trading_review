import streamlit as st
import requests
import json
from datetime import datetime

# 配置请求参数
BASE_URL = "https://apphwhq.longhuvip.com/w1/api/index.php"

HEADERS = {
    "Host": "apphwhq.longhuvip.com",
    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    "User-Agent": "lhb/5.17.9 (com.kaipanla.www; build:0; iOS 16.6.0) Alamofire/4.9.1",
    "Accept": "*/*",
    "Accept-Language": "zh-Hans-CN;q=1.0",
    "Accept-Encoding": "gzip;q=1.0, compress;q=0.5",
    "Connection": "keep-alive"
}

FORM_DATA = {
    "PhoneOSNew": 2,
    # "Token": "xxxx",
    # "UserID": "xxxx",
    "VerSion": "5.17.0.9",
    "View": "2,4,5,7,10",
    "a": "GetInfo",
    "apiv": "w38",
    "c": "Index"
}


@st.cache_data(ttl=300, show_spinner="正在获取最新数据...")
def fetch_data():
    """发送POST请求并处理响应"""
    try:
        st.toast("正在请求数据接口...")
        response = requests.post(
            BASE_URL,
            data=FORM_DATA,
            headers=HEADERS,
            timeout=15,
            verify=True
        )

        st.toast(f"收到响应状态码: {response.status_code}")
        if response.status_code != 200:
            st.error(f"接口返回异常状态码: {response.status_code}")
            return None

        try:
            json_data = response.json()
            st.toast("数据解析成功")
            return json_data
        except json.JSONDecodeError:
            st.error("响应数据不是有效的JSON格式")
            st.write("原始响应内容:", response.text[:200])
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"网络请求失败: {str(e)}")
        return None
    except Exception as e:
        st.error(f"未知错误: {str(e)}")
        return None


def parse_response(data):
    """解析API响应数据"""
    try:
        # 调试输出原始数据结构
        st.session_state.raw_data = data

        parsed = {
            "bace_face_list": [],
            "da_ban_stats": {},
            "weather_vane": {"up": [], "down": []},
            "phb_list": [],
            "update_time": "未知"
        }

        # 解析时间戳
        if "Time" in data:
            try:
                parsed["update_time"] = datetime.fromtimestamp(data["Time"]).strftime("%Y-%m-%d %H:%M:%S")
            except:
                parsed["update_time"] = "时间格式错误"

        # 解析BaceFaceList
        if "BaceFaceList" in data and isinstance(data["BaceFaceList"], list):
            for item in data["BaceFaceList"]:
                if len(item) >= 3:
                    parsed["bace_face_list"].append({
                        "name": str(item[0]),
                        "value": str(item[1]),
                        "id": str(item[2])
                    })

        # 解析DaBanList
        if "DaBanList" in data and isinstance(data["DaBanList"], dict):
            parsed["da_ban_stats"] = {
                "total_zhangting": data["DaBanList"].get("tZhangTing", "N/A"),
                "latest_zhangting": data["DaBanList"].get("lZhangTing", "N/A"),
                "total_fengban": data["DaBanList"].get("tFengBan", "N/A"),
                "latest_fengban": data["DaBanList"].get("lFengBan", "N/A"),
                "total_dieting": data["DaBanList"].get("tDieTing", "N/A"),
                "latest_dieting": data["DaBanList"].get("lDieTing", "N/A"),
                "heat_index": data["DaBanList"].get("ZHQD", "N/A")
            }

        # 解析风向标
        if "CWeatherVaneList" in data:
            for market in ["SZ", "XD"]:
                if market in data["CWeatherVaneList"]:
                    for item in data["CWeatherVaneList"][market]:
                        if len(item) >= 4:
                            entry = {
                                "code": str(item[0]),
                                "name": str(item[1]),
                                "change": f"{float(item[2]):.2f}%" if isinstance(item[2], (int, float)) else str(
                                    item[2]),
                                "sector": str(item[3])
                            }
                            parsed["weather_vane"]["up" if market == "SZ" else "down"].append(entry)

        # 解析排行榜
        if "PHBList" in data and isinstance(data["PHBList"], list):
            for item in data["PHBList"]:
                if len(item) >= 6:
                    parsed["phb_list"].append({
                        "code": str(item[0]),
                        "name": str(item[1]),
                        "change": f"{float(item[2]):.2f}%" if isinstance(item[2], (int, float)) else str(item[2]),
                        "days": str(item[3]),
                        "type": str(item[4]),
                        "concept": str(item[5])
                    })

        return parsed

    except Exception as e:
        st.error(f"数据解析失败: {str(e)}")
        st.write("解析失败时的数据片段:", json.dumps(data, ensure_ascii=False)[:300])
        return None


def main():
    st.set_page_config(
        page_title="股市实时监控看板",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📈 股市实时监控看板")
    st.markdown("---")

    # 获取数据
    raw_data = fetch_data()
    print(raw_data)

    if not raw_data:
        st.error("数据获取失败，请检查：")
        st.markdown("""
        1. 网络连接是否正常
        2. 是否使用了VPN/代理
        3. 尝试刷新页面
        4. 如果持续失败，可能是接口不可用
        """)
        return

    data = parse_response(raw_data)
    if not data:
        st.error("数据解析失败，原始数据结构：")
        st.json(raw_data)
        return

    # 显示基础信息
    st.subheader(f"市场数据 @ {data['update_time']}")

    # 关键指标卡片
    cols = st.columns(4)
    metrics = [
        ("涨停数", data["da_ban_stats"]["latest_zhangting"], "#4CAF50"),
        ("跌停数", data["da_ban_stats"]["latest_dieting"], "#F44336"),
        ("封板率", f"{data['da_ban_stats']['latest_fengban']}%", "#2196F3"),
        ("市场热度", data["da_ban_stats"]["heat_index"], "#FF9800")
    ]

    for col, (title, value, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div style='
                padding: 20px;
                background: {color}10;
                border-radius: 10px;
                border-left: 5px solid {color};
                margin: 10px 0;
            '>
                <h3 style='color: {color}; margin:0;'>{title}</h3>
                <h1 style='color: {color}; margin:0;'>{value}</h1>
            </div>
            """, unsafe_allow_html=True)

    # 数据表格展示
    tab1, tab2, tab3 = st.tabs(["📈 领涨板块", "📉 领跌板块", "🏆 连板排行"])

    with tab1:
        if data["weather_vane"]["up"]:
            st.dataframe(
                data["weather_vane"]["up"],
                column_config={
                    "code": "代码",
                    "name": "名称",
                    "change": "涨幅",
                    "sector": "板块"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("暂无领涨数据")

    with tab2:
        if data["weather_vane"]["down"]:
            st.dataframe(
                data["weather_vane"]["down"],
                column_config={
                    "code": "代码",
                    "name": "名称",
                    "change": "跌幅",
                    "sector": "板块"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("暂无领跌数据")

    with tab3:
        if data["phb_list"]:
            st.dataframe(
                data["phb_list"],
                column_config={
                    "code": "代码",
                    "name": "名称",
                    "change": "涨幅",
                    "days": "天数",
                    "type": "类型",
                    "concept": "概念"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("当前无连板数据")

    # 热门概念展示
    with st.expander("🔥 热门概念", expanded=True):
        if data["bace_face_list"]:
            for item in data["bace_face_list"]:
                try:
                    value = float(item["value"].replace("%", ""))
                except:
                    value = 0

                st.markdown(f"""
                <div style='
                    margin: 10px 0;
                    padding: 10px;
                    background: #f0f2f6;
                    border-radius: 8px;
                '>
                    <div style='
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 5px;
                    '>
                        <span>{item['name']}</span>
                        <span>{item['value']}</span>
                    </div>
                    <div style='
                        height: 20px;
                        background: #e0e0e0;
                        border-radius: 10px;
                        overflow: hidden;
                    '>
                        <div style='
                            width: {value}%;
                            height: 100%;
                            background: linear-gradient(90deg, #2196F3, #03A9F4);
                            transition: width 0.5s ease;
                        '></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("暂无热门概念数据")


if __name__ == "__main__":
    main()