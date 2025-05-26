import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# 配置请求参数
BASE_URL = "https://applhb.longhuvip.com/w1/api/index.php"
HEADERS = {
    "Host": "applhb.longhuvip.com",
    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    "User-Agent": "lhb/5.17.9 (com.kaipanla.www; build:0; iOS 16.6.0) Alamofire/4.9.1",
    "Accept": "*/*",
    "Accept-Language": "zh-Hans-CN;q=1.0",
    "Accept-Encoding": "gzip;q=1.0, compress;q=0.5",
    "Connection": "keep-alive"
}

BASE_PARAMS = {
    "PhoneOSNew": 2,
    "VerSion": "5.17.0.9",
    "View": "2,4,5,7,10",
    "a": "InfoGet",
    "apiv": "w38",
    "c": "Theme"
}


def fetch_concept(concept_id):
    """获取单个概念数据，包含调试信息"""
    debug_info = {
        "概念ID": concept_id,
        "处理状态": "失败",
        "错误信息": None,
        "原始数据": None,
        "有效数据": None
    }

    try:
        response = requests.post(
            BASE_URL,
            headers=HEADERS,
            data={**BASE_PARAMS, "ID": str(concept_id)},
            timeout=10
        )

        debug_info["响应状态码"] = response.status_code

        if response.status_code == 200:
            data = response.json()
            debug_info["原始数据"] = data  # 保留原始数据

            if data.get('errcode') == '0':
                # 通用字段
                concept_name = data.get('Name', '未知概念')
                class_layer = data.get('ClassLayer', '1')

                # 初始化结果结构
                result = {
                    "概念ID": concept_id,
                    "概念名称": concept_name,
                    "分层结构": [],
                    "股票列表": []
                }

                # 分层处理逻辑
                if class_layer == "2":
                    # 处理Table中的分层结构
                    for table in data.get('Table', []):
                        level1 = table.get('Level1', {})
                        level2_list = table.get('Level2', [])

                        # 处理Level1
                        level1_data = {
                            "层级": "Level1",
                            "分类ID": level1.get('ID'),
                            "分类名称": level1.get('Name'),
                            "股票列表": [
                                (s['StockID'], s['prod_name'])
                                for s in level1.get('Stocks', [])
                            ]
                        }
                        result["分层结构"].append(level1_data)

                        # 处理Level2
                        for level2 in level2_list:
                            level2_data = {
                                "层级": "Level2",
                                "分类ID": level2.get('ID'),
                                "分类名称": level2.get('Name'),
                                "股票列表": [
                                    (s['StockID'], s['prod_name'])
                                    for s in level2.get('Stocks', [])
                                ]
                            }
                            result["分层结构"].append(level2_data)

                # 通用股票处理
                stock_sources = []
                if data.get('Stocks'):
                    stock_sources.append(data['Stocks'])
                # if data.get('StockList'):
                #     stock_sources.append(data['StockList'])

                for source in stock_sources:
                    for stock in source:
                        if isinstance(stock, dict):
                            result["股票列表"].append((
                                stock.get('StockID', '未知代码'),
                                stock.get('prod_name', '未知名称')
                            ))

                debug_info.update({
                    "处理状态": "成功",
                    "有效数据": result
                })
            else:
                debug_info["错误信息"] = f"接口返回错误码: {data.get('errcode')}"
        else:
            debug_info["错误信息"] = f"HTTP错误: {response.status_code}"

    except Exception as e:
        debug_info["错误信息"] = f"请求异常: {str(e)}"

    return debug_info


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_concepts(max_id=300):
    """批量获取所有概念数据"""
    results = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, concept_id in enumerate(range(1, max_id + 1), 1):
        progress = idx / max_id
        progress_bar.progress(progress,
                              text=f"扫描进度: {idx}/{max_id} | 有效概念: {len([r for r in results if r['处理状态'] == '成功'])}"
                              )

        debug_data = fetch_concept(concept_id)
        results.append(debug_data)

    progress_bar.empty()
    return results


def app():


    st.title("🔍 全量概念股数据扫描")




    max_id = st.number_input(
        "最大概念ID",
        min_value=1,
        max_value=500,
        value=312,
        help="设置需要扫描的最大概念ID号"
    )
    with st.spinner(f'正在扫描1-{max_id}号概念板块...'):
        debug_results = fetch_all_concepts(max_id)

        # 统计面板
        success_count = len([r for r in debug_results if r['处理状态'] == '成功'])
        st.success(f"扫描完成！成功获取 {success_count} 个概念，失败 {len(debug_results) - success_count} 个")


        # 有效数据处理
        valid_data = []
        for result in debug_results:
            if result["处理状态"] == "成功" and result["有效数据"]:
                # 处理分层数据
                for layer in result["有效数据"]["分层结构"]:
                    for stock_id, stock_name in layer["股票列表"]:
                        valid_data.append({
                            "概念ID": result["有效数据"]["概念ID"],
                            "概念名称": result["有效数据"]["概念名称"],
                            "分类层级": layer["层级"],
                            "分类ID": layer["分类ID"],
                            "分类名称": layer["分类名称"],
                            "股票代码": stock_id,
                            "股票名称": stock_name
                        })

                # 处理通用股票数据
                for stock_id, stock_name in result["有效数据"]["股票列表"]:
                    valid_data.append({
                        "概念ID": result["有效数据"]["概念ID"],
                        "概念名称": result["有效数据"]["概念名称"],
                        "分类层级": "通用",
                        "分类ID": None,
                        "分类名称": None,
                        "股票代码": stock_id,
                        "股票名称": stock_name
                    })

        if valid_data:
            df = pd.DataFrame(valid_data).drop_duplicates()

            # 展示数据
            st.dataframe(
                df,
                use_container_width=True,
                height=600,
                column_config={
                    "概念ID": st.column_config.NumberColumn(width="50px"),
                    "概念名称": st.column_config.TextColumn(width="200px"),
                    "分类层级": st.column_config.TextColumn(width="80px"),
                    "分类名称": st.column_config.TextColumn(width="150px"),
                    "股票代码": st.column_config.TextColumn(width="100px"),
                }
            )

            # 导出数据
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "导出CSV",
                csv,
                file_name=f"concept_stocks_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("未发现有效股票数据")


if __name__ == "__main__":
    app()