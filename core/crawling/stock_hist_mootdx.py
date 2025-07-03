from mootdx.reader import Reader

# market: 参数 `std` 为标准市场(就是股票), `ext` 为扩展市场(期货，黄金等)
# tdxdir: 是通达信的数据目录, 根据自己的情况修改

reader = Reader.factory(market='std', tdxdir='/mnt/c/new_tdx')

# 读取日线数据
data = reader.daily(symbol='600036')
print(data)

# 读取分钟数据
data = reader.minute(symbol='600036')
print(data)

# 读取时间线数据
data = reader.fzline(symbol='600036')
print(data)