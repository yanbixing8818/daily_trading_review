import baostock as bs
import pandas as pd

# 登陆系统
lg = bs.login()
# 显示登陆返回信息
print(lg.error_code)
print(lg.error_msg)
# 详细指标参数，参见“历史行情指标参数”章节
rs = bs.query_history_k_data_plus("sz.300651",
    "date,code,open,high,low,close,volume,amount,adjustflag",
    start_date='2025-05-01', end_date='2025-06-07',
    frequency="d", adjustflag="3")
print(rs.error_code)
print(rs.error_msg)
# 获取具体的信息
result_list = []
while (rs.error_code == '0') & rs.next():
    # 分页查询，将每页信息合并在一起
    result_list.append(rs.get_row_data())
result = pd.DataFrame(result_list, columns=rs.fields)
result.to_csv("./history_k_data.csv", encoding="gbk", index=False)
print(result)
# 登出系统
bs.logout()