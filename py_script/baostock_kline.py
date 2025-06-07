# 获取股票数据
import baostock as bs
import pandas as pd
import mplfinance as mpf

lg = bs.login()

rs = bs.query_history_k_data_plus("sz.300651",
    "date,open,high,low,close",
    start_date='2025-05-01', end_date='2025-06-07',
    frequency="d", adjustflag="2")

data_list = []
while (rs.error_code == '0') & rs.next():
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)

# 将date转为索引
result['date'] = pd.to_datetime(result['date'])
result.set_index('date', inplace=True)

# 更换字段类型
for col in ['open', 'high', 'low', 'close']:
    result[col] = result[col].astype(float)

bs.logout()


moving_averages = [5,10,15] # 需要绘制的均线

mpf.plot(result,
         type='candle',
         mav=moving_averages,
         savefig='kline.jpg')