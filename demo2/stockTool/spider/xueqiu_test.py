import requests
from multiprocessing import Pool

def get_dynamic(user_id, page='1', md5=''):
    try:

        url = "https://xueqiu.com/v4/statuses/user_timeline.json"
        params = {
            "page": page,
            "user_id": "9887656769",
            "md5__1038": "n4+xyD9DuDRDcACdDsD7I5D=aFa2uD0hDxTD",
            "screen_name": "轮回666"
        }

        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Referer": "https://xueqiu.com/u/9887656769?md5__1038=n4+xuD0DRDgGjhDjx05+bDyDAOhbeDBY=hoD",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            'Cookie':'cookiesu=791733375352695; device_id=f209dddad001c71ee26c2dc5056fad28; s=bs11d1num8; .thumbcache_f24b8bbe5a5934237bbc0eda20c1b6e7=; smidV2=20241205130913c3c3e1f023d380e39375df3fabde7b07008e42f93486db070; Hm_lvt_1db88642e346389874251b5a1eded6e3=1737801078,1738484224,1740188425; HMACCOUNT=3CC7F77EFB6ED364; remember=1; xq_a_token=c3dd069a2b2de0cd3c80463907eab09d50eded07; xqat=c3dd069a2b2de0cd3c80463907eab09d50eded07; xq_id_token=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ1aWQiOjgyNzAwMTI1NzQsImlzcyI6InVjIiwiZXhwIjoxNzQyNzgxMDY2LCJjdG0iOjE3NDAxODkwNjY5MjQsImNpZCI6ImQ5ZDBuNEFadXAifQ.ngdbYDBltnWW3iZgO46mCmFuMQqazZQ3JpDsC0dazddR8rfAUivyOIguejVKKCZnck1c7QTTnnMbOccW_OHOT7Lwen62nSvTqdn2oVIjDZzPii6ZRARceGt1jznxnTyRQpDX-GkjOjIZlZWKcVQrjOudAJW7FlcyKU_jNsKfeKqyAnn9SlJ48B1o4BOfQixpulGPDNymonFlY3Gb3Uz9oYvDLQ0nHMAmtAuv7u9EGPf0m-rWKYY2Ur7tpg8QBvuJ0CdIdAGINSd1f0qEDkHXW_cc__44jYlkXc4xqsd0TJOGp0Gmfebzr7g5t7m1vWUYuCn5k_6DFGU-rkCDULl9Gw; xq_r_token=766de6babb9a66785ea1806aa03fde155e7211b5; xq_is_login=1; u=8270012574; acw_tc=ac11000117402046308482755e008b455cb6f9bdc1a320b8230048d424d8d9; ssxmod_itna=YuD=PfohCGk3GHqGdD7IqYYIH1WaDIE40Ip06=D/niGDnqD=GFDK40oAg4DCfmlGDe4a4raGWxa=8WrPbpQ1ta4eD=xYQDwxYoDUxGtDpxG6=VDen=D5xGoDPxDeDAGKDC9odKDd2aMFtLeqQjYdtDmbQXDGQ2DiU5xi5V0TXBj8GBDD35xB6/DA3XD7tMeTdDbqDuiajPwqDLzCWWMndDbrpcSjTDtuRXn84SUdN2UP+rWOeY/ODz8FpsniqzCBg3FY4qiAxz/iwPnYpEkFusIFD===; ssxmod_itna2=YuD=PfohCGk3GHqGdD7IqYYIH1WaDIE40Ip0=G9bLDBdP7QHGcDeLbD=; Hm_lpvt_1db88642e346389874251b5a1eded6e3=1740205431'
        }


        response = requests.get(url, params=params, headers=headers)
        print(response.text)
        response.raise_for_status()

        # 检查响应内容是否为空
        if not response.text.strip():
            print(f"页面 {page} 的响应内容为空")
            return []

        data = response.json()
        return [item["description"] for item in data["statuses"]]
    except requests.RequestException as e:
        print(f"请求出错: {e}")
    except (KeyError, ValueError) as e:
        print(f"数据解析出错: {e}")
    return []

if __name__ == "__main__":
    user_id = '9887656769'  # 替换为正确的 user_id
    md5='n4%2BxyD9DuDRDcACdDsD7I5D%3DaFax020gwhxTD'
    pages = range(1, 6)
    for page in pages:
        descriptions = get_dynamic(user_id, page=page, md5=md5)
        for desc in descriptions:
            print(desc)
    # with Pool(4) as p:
    #     results = p.starmap(get_dynamic, [(user_id, i) for i in pages])
    # all_descriptions = [desc for sublist in results for desc in sublist]
    # for desc in all_descriptions:
    #     print(desc)