import pandas as pd
import pywencai

def fetch_and_save_wencai(query, output_file):
    """查询问财，按行业分组统计数量和股票列表，并保存到Excel"""
    result = pywencai.get(query=query, sort_key='成交金额', sort_order='desc')
    if result is None or len(result) == 0:
        print(f"未获取到数据：{query}")
        return
    df = pd.DataFrame(result)
    if '行业简称' not in df.columns or '股票简称' not in df.columns:
        print(f"缺少必要字段，实际字段为：{df.columns}")
        return
    grouped = df.groupby('行业简称')['股票简称'].agg(['count', lambda x: '，'.join(x)]).reset_index()
    grouped.columns = ['行业简称', '数量', '股票列表']
    grouped = grouped.sort_values(by='数量', ascending=False)
    grouped.to_excel(output_file, index=False)
    print(f"已输出到 {output_file}")

if __name__ == "__main__":
    fetch_and_save_wencai(
        query="今日收盘价创历史新高股票，按照同花顺行业排序",
        output_file="今日收盘新高股票_行业统计.xlsx"
    )
    fetch_and_save_wencai(
        query="今日收盘价创120日新高股票，按照同花顺行业排序",
        output_file="今日收盘120日新高股票_行业统计.xlsx"
    )
