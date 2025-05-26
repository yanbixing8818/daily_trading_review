import requests
import json
from pprint import pprint

url = "https://np-pick-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code"


payload = {
    "keyWord": "涨停;",
    "pageSize": 50,
    "pageNo": 1,
    "fingerprint": "换成自己的",
    "gids": [],
    "matchWord": "",
    "timestamp": "1741616054584362",
    "shareToGuba": False,
    "requestId": "xxxxx",
    "needCorrect": True,
    "removedConditionIdList": [],
    "xcId": "xxxxxxx",
    "ownSelectAll": False
}

# 添加通用请求头（部分 API 需要特定头信息）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/"
}

try:
    # 发送 POST 请求（使用 json 参数自动处理编码）
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=10  # 设置超时时间
    )

    # 检查 HTTP 状态码
    response.raise_for_status()

    # 解析并打印响应内容
    print("\n响应状态码:", response.status_code)
    print("响应内容（原始JSON）:")
    pprint(response.json())  # 使用 pprint 美化输出

except requests.exceptions.RequestException as e:
    print(f"请求失败: {str(e)}")
except json.JSONDecodeError:
    print("响应内容非 JSON 格式，原始响应:", response.text)