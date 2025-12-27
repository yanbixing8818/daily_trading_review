from mootdx.reader import Reader
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# 设置中文字体（解决画图中文显示问题）
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

def get_local_stock_data(stock_code, tdx_data_path, start_date=None, end_date=None):
    """
    从mootdx读取本地通达信数据
    :param stock_code: 股票代码（如"600036"或"600519"）
    :param tdx_data_path: 通达信本地数据目录（如 "E:/new_tdx"）
    :param start_date: 开始日期（格式"YYYY-MM-DD"）
    :param end_date: 结束日期（格式"YYYY-MM-DD"）
    :return: 包含OHLC的DataFrame
    """
    try:
        # 创建mootdx Reader
        reader = Reader.factory(market='std', tdxdir=tdx_data_path)
        
        # 读取日线数据（mootdx可以直接使用股票代码，不需要市场前缀）
        df = reader.daily(symbol=stock_code)
        
        if df is None or df.empty:
            raise ValueError(f"股票{stock_code}数据为空，请检查代码是否正确或数据是否存在")
        
        print(f"成功读取本地数据：{stock_code}，共{len(df)}条记录")
        print(f"数据列名：{list(df.columns)}")
        
        # 处理日期列：mootdx返回的DataFrame可能日期在列中或索引中
        if 'date' not in df.columns:
            # 尝试从索引中恢复日期
            if df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()  # 将索引转为列
            # 特殊处理：某些版本返回'日期'中文列名
            elif '日期' in df.columns:
                df = df.rename(columns={'日期': 'date'})
            else:
                raise ValueError(f"无法找到日期列，现有列：{list(df.columns)}，索引：{df.index.name}")
        
        # 转换日期格式
        try:
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            # 尝试解析常见日期格式
            try:
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')  # 处理20250711格式
            except:
                raise ValueError(f"日期转换失败: {str(e)}")
        
        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必要列：{col}，现有列：{list(df.columns)}")
        
        # 排序并过滤空值
        df = df.sort_values('date').dropna(subset=['date'])
        
        # 重要：为了计算指标，需要使用全部历史数据，而不是只从start_date往前推
        # 这样可以确保末尾日期的指标计算准确
        # 如果指定了start_date，我们仍然使用全部数据计算，最后再筛选显示
        print(f"读取到的全部数据：{len(df)}条，日期范围：{df['date'].min()} 至 {df['date'].max()}")
        
        # 如果数据量太少，给出警告
        if len(df) < 100:
            print(f"警告：数据量只有{len(df)}天，可能不足以准确计算所有指标（特别是风险指标需要较多历史数据）")
        
        # 将日期转为字符串格式（YYYY-MM-DD）
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        # 重置索引
        df.reset_index(drop=True, inplace=True)
        
        # 保留核心列
        df = df[['date', 'open', 'high', 'low', 'close']]
        
        # 注意：这里返回的是包含历史数据的完整DataFrame
        # 日期筛选会在计算完指标后进行
        return df
    
    except Exception as e:
        raise Exception(f"读取本地数据失败：{str(e)}")

def calculate_stock_indicator(df):
    """
    计算通达信公式对应的股票指标（复用之前的计算逻辑）
    :param df: 包含date/open/high/low/close的DataFrame
    :return: 包含所有指标的DataFrame
    """
    # 检查数据量是否足够（至少需要90天用于VAR6计算，建议252天以上）
    min_required_days = 90
    if len(df) < min_required_days:
        print(f"警告：数据量不足{min_required_days}天（当前{len(df)}天），计算结果可能不准确")
    
    print(f"开始计算指标，数据量：{len(df)}天，日期范围：{df['date'].iloc[0]} 至 {df['date'].iloc[-1]}")
    # 定义SMA函数（通达信SMA，参数：x序列, n周期, m权重，默认m=1）
    # 通达信SMA公式：SMA(x, n, m) = (m*x + (n-m)*SMA_prev) / n
    # 这是一个递归公式，需要使用循环计算
    def sma(x, n, m=1):
        if not isinstance(x, pd.Series):
            x = pd.Series(x)
        result = pd.Series(index=x.index, dtype=float)
        
        # 找到第一个非NaN值的位置
        first_valid_idx = x.first_valid_index()
        if first_valid_idx is None:
            # 如果全部是NaN，返回全NaN
            return result
        
        first_valid_pos = x.index.get_loc(first_valid_idx)
        
        # 第一个有效值等于x的第一个有效值
        result.iloc[first_valid_pos] = x.iloc[first_valid_pos]
        
        # 递归计算后续值
        for i in range(first_valid_pos + 1, len(x)):
            prev_sma = result.iloc[i-1]
            if pd.isna(prev_sma) or pd.isna(x.iloc[i]):
                result.iloc[i] = np.nan
            else:
                result.iloc[i] = (m * x.iloc[i] + (n - m) * prev_sma) / n
        
        return result
    
    # 定义EMA函数（指数移动平均，适配通达信EMA）
    def ema(x, n):
        # 确保输入是pandas Series
        if not isinstance(x, pd.Series):
            # 如果x是numpy数组，需要提供索引
            if isinstance(x, np.ndarray):
                x = pd.Series(x, index=df.index)
            else:
                x = pd.Series(x)
        return x.ewm(span=n, adjust=False).mean()
    
    # 定义MA函数（简单移动平均，同花顺MA函数）
    def ma(x, n):
        return x.rolling(window=n).mean()
    
    # VAR1:=REF(LOW,1)  # 前1日最低价
    df['VAR1'] = df['low'].shift(1)
    # 处理VAR1的第一个NaN值（用第一个low值填充，或者保持NaN但后续计算时处理）
    # 注意：REF函数在第一个值确实是NaN，但为了计算，我们可以用第一个low值填充
    # 或者保持NaN，在SMA计算时处理
    
    # VAR2:=SMA(ABS(LOW-VAR1),3,1)/SMA(MAX(LOW-VAR1,0),3,1)*100
    df['abs_low_var1'] = np.abs(df['low'] - df['VAR1'])
    df['max_low_var1'] = np.maximum(df['low'] - df['VAR1'], 0)
    
    # 调试信息：检查输入数据
    print(f"\n调试信息 - VAR1和输入数据统计：")
    print(f"  VAR1第一个值：{df['VAR1'].iloc[0]}, 前5个值：{df['VAR1'].head(5).tolist()}")
    print(f"  abs_low_var1前5个值：{df['abs_low_var1'].head(5).tolist()}")
    print(f"  max_low_var1前5个值：{df['max_low_var1'].head(5).tolist()}")
    print(f"  abs_low_var1 NaN数量：{df['abs_low_var1'].isna().sum()}")
    print(f"  max_low_var1 NaN数量：{df['max_low_var1'].isna().sum()}")
    
    sma_abs = sma(df['abs_low_var1'], 3, 1)
    sma_max = sma(df['max_low_var1'], 3, 1)
    # 处理除零情况
    df['VAR2'] = np.where(sma_max != 0, sma_abs / sma_max * 100, 0)
    df['VAR2'] = df['VAR2'].fillna(0)
    
    # 调试信息：检查VAR2的值
    print(f"\n调试信息 - VAR2统计：")
    print(f"  VAR2最大值：{df['VAR2'].max():.4f}, 平均值：{df['VAR2'].mean():.4f}")
    print(f"  VAR2非零数量：{(df['VAR2'] != 0).sum()} / {len(df)}")
    print(f"  VAR2最后10行：{df['VAR2'].tail(10).tolist()}")
    print(f"  sma_abs最后10行：{sma_abs.tail(10).tolist()}")
    print(f"  sma_max最后10行：{sma_max.tail(10).tolist()}")
    
    # VAR3:=EMA(IF(CLOSE*1.2,VAR2*10,VAR2/10),3)
    # 注意：同花顺中IF(CLOSE*1.2, ...)表示如果CLOSE*1.2非0则为真
    # 由于股票价格CLOSE不会为0，所以CLOSE*1.2永远非0，条件永远为真
    # 这意味着VAR3实际上总是等于EMA(VAR2*10, 3)
    # 如果原始公式有误，可能是IF(CLOSE>1.2*REF(CLOSE,1), ...)或其他条件
    # 这里严格按照原始公式实现
    var3_condition = pd.Series(np.where(df['close'] * 1.2 != 0,  # CLOSE*1.2非0为真（实际永远为真）
                                        df['VAR2']*10, df['VAR2']/10), index=df.index)
    df['VAR3'] = ema(var3_condition, 3)
    
    # VAR4:=LLV(LOW,38)  # 38日最低价的最低值
    df['VAR4'] = df['low'].rolling(window=38).min()
    
    # VAR5:=HHV(VAR3,38)  # 38日VAR3的最高值
    df['VAR5'] = df['VAR3'].rolling(window=38).max()
    
    # VAR6:=IF(LLV(LOW,90),1,0)
    # 注意：原始公式IF(LLV(LOW,90),1,0)在同花顺中，如果LLV(LOW,90)返回的数值非0（即90日最低价存在），则为1
    # 由于90日最低价几乎总是存在且非0，所以VAR6应该几乎总是1
    # 这样VAR7才能正常计算，否则如果VAR6全为0，VAR7就会全为0
    df['llv_low_90'] = df['low'].rolling(window=90).min()
    # 如果90日最低价存在且非0，则为1（这样VAR6在数据充足时几乎总是1）
    df['VAR6'] = np.where((df['llv_low_90'].notna()) & (df['llv_low_90'] != 0), 1, 0)
    
    # 调试信息：检查VAR6的值
    var6_count = df['VAR6'].sum()
    print(f"VAR6统计：共有{var6_count}个交易日创90日新低（VAR6=1）")
    if var6_count == 0:
        print("警告：VAR6全为0，这会导致VAR7（主力吸货）全为0")
        print("这可能是因为在筛选的日期范围内，没有创90日新低的情况")
    
    # VAR7:=EMA(IF(LOW<=VAR4,(VAR3+VAR5*2)/2,0),3)/618*VAR6
    # 调试信息：检查VAR3、VAR4、VAR5的值
    print(f"\n调试信息 - VAR3/VAR4/VAR5统计（最后10行）：")
    print(f"  VAR3最大值：{df['VAR3'].max():.4f}, 平均值：{df['VAR3'].mean():.4f}, 最后10行：{df['VAR3'].tail(10).tolist()}")
    print(f"  VAR4最大值：{df['VAR4'].max():.4f}, 平均值：{df['VAR4'].mean():.4f}, 最后10行：{df['VAR4'].tail(10).tolist()}")
    print(f"  VAR5最大值：{df['VAR5'].max():.4f}, 平均值：{df['VAR5'].mean():.4f}, 最后10行：{df['VAR5'].tail(10).tolist()}")
    print(f"  LOW最后10行：{df['low'].tail(10).tolist()}")
    
    # 检查条件 LOW<=VAR4 的满足情况
    low_le_var4 = (df['low'] <= df['VAR4']).sum()
    print(f"  条件LOW<=VAR4满足的次数：{low_le_var4} / {len(df)}")
    
    # 计算var7_temp
    df['var7_temp'] = pd.Series(np.where(df['low'] <= df['VAR4'], (df['VAR3'] + df['VAR5']*2)/2, 0), index=df.index)
    df['var7_temp'] = df['var7_temp'].fillna(0)  # 处理NaN值
    
    # 调试信息：检查var7_temp
    print(f"  var7_temp最大值：{df['var7_temp'].max():.4f}, 平均值：{df['var7_temp'].mean():.4f}, 非零数量：{(df['var7_temp'] != 0).sum()}")
    print(f"  var7_temp最后10行：{df['var7_temp'].tail(10).tolist()}")
    
    df['var7_ema'] = ema(df['var7_temp'], 3)  # 先计算EMA部分
    df['VAR7'] = df['var7_ema'] / 618 * df['VAR6']
    df['VAR7'] = df['VAR7'].fillna(0)  # 处理最终结果的NaN
    
    # 调试信息：检查VAR7的计算过程
    print(f"\nVAR7统计：最大值={df['VAR7'].max():.4f}, 平均值={df['VAR7'].mean():.4f}")
    print(f"VAR7_EMA统计：最大值={df['var7_ema'].max():.4f}, 平均值={df['var7_ema'].mean():.4f}")
    
    # VAR8:=((C-LLV(L,21))/(HHV(H,21)-LLV(L,21)))*100
    # 注意：同花顺的LLV(L,21)和HHV(H,21)通常是指过去21天（不包括今天）
    # 使用shift(1)来排除当前日期，计算过去21天的最值
    # 先计算过去21天的最值（不包括今天）
    df['llv_l21_past'] = df['low'].shift(1).rolling(window=21, min_periods=1).min()
    df['hhv_h21_past'] = df['high'].shift(1).rolling(window=21, min_periods=1).max()
    # 如果shift后第一个值是NaN，用第一个有效值填充
    df['llv_l21_past'] = df['llv_l21_past'].bfill().fillna(df['low'].iloc[0] if len(df) > 0 else 0)
    df['hhv_h21_past'] = df['hhv_h21_past'].bfill().fillna(df['high'].iloc[0] if len(df) > 0 else 0)
    
    # 同时保留包含今天的计算方式（用于对比）
    df['llv_l21'] = df['low'].rolling(window=21, min_periods=1).min()
    df['hhv_h21'] = df['high'].rolling(window=21, min_periods=1).max()
    
    # 尝试使用过去21天（不包括今天）的方式计算VAR8
    df['VAR8_past'] = (df['close'] - df['llv_l21_past']) / (df['hhv_h21_past'] - df['llv_l21_past']) * 100
    df['VAR8_past'] = df['VAR8_past'].replace([np.inf, -np.inf], 0).fillna(0)
    
    # 使用包含今天的计算方式（原逻辑）
    df['VAR8'] = (df['close'] - df['llv_l21']) / (df['hhv_h21'] - df['llv_l21']) * 100
    # 处理分母为0的情况（避免除0错误）
    df['VAR8'] = df['VAR8'].replace([np.inf, -np.inf], 0).fillna(0)
    
    # 调试信息：对比两种计算方式
    check_date_str = '2025-12-19'
    if check_date_str in df['date'].values:
        check_idx = df[df['date'] == check_date_str].index[0]
        row = df.iloc[check_idx]
        print(f"\n  调试信息 - 19号VAR8计算对比：")
        print(f"    包含今天：LLV21={row['llv_l21']:.2f}, HHV21={row['hhv_h21']:.2f}, VAR8={row['VAR8']:.4f}")
        print(f"    过去21天：LLV21={row['llv_l21_past']:.2f}, HHV21={row['hhv_h21_past']:.2f}, VAR8={row['VAR8_past']:.4f}")
    
    # 使用包含今天的21日窗口计算方式
    # 注意：这里使用包含今天的计算方式，即LLV(L,21)和HHV(H,21)包含当前日期
    # df['llv_l21'] 和 df['hhv_h21'] 已经是包含今天的计算方式
    # df['VAR8'] 已经是基于包含今天的计算方式
    # 不需要重新赋值，直接使用上面计算的包含今天的值
    
    # 调试信息：验证19号的VAR8计算
    check_date_str = '2025-12-19'
    if check_date_str in df['date'].values:
        check_idx = df[df['date'] == check_date_str].index[0]
        if check_idx >= 20:  # 确保有足够的历史数据
            print(f"\n  调试信息 - 验证19号的VAR8计算：")
            row = df.iloc[check_idx]
            # 手动计算21日窗口
            window_start = max(0, check_idx - 20)
            window_data = df.iloc[window_start:check_idx+1]
            manual_llv = window_data['low'].min()
            manual_hhv = window_data['high'].max()
            manual_var8 = (row['close'] - manual_llv) / (manual_hhv - manual_llv) * 100 if (manual_hhv - manual_llv) != 0 else 0
            print(f"    19号数据：close={row['close']:.2f}, low={row['low']:.2f}, high={row['high']:.2f}")
            print(f"    21日窗口（包含19号）：LLV21={manual_llv:.2f}, HHV21={manual_hhv:.2f}")
            print(f"    程序计算的LLV21={row['llv_l21']:.2f}, HHV21={row['hhv_h21']:.2f}")
            print(f"    手动计算VAR8=(({row['close']:.2f}-{manual_llv:.2f})/({manual_hhv:.2f}-{manual_llv:.2f}))*100 = {manual_var8:.4f}")
            print(f"    程序计算的VAR8={row['VAR8']:.4f}, 差异={abs(manual_var8 - row['VAR8']):.6f}")
    
    # VAR9:=SMA(VAR8,13,8)
    # 严格按照公式计算，SMA函数会自然处理NaN值
    df['VAR9'] = sma(df['VAR8'], 13, 8)
    
    # 调试信息：检查风险指标的计算过程
    print(f"\n调试信息 - 风险指标计算过程：")
    print(f"  VAR8统计：最大值={df['VAR8'].max():.4f}, 平均值={df['VAR8'].mean():.4f}, 最后10行：{df['VAR8'].tail(10).tolist()}")
    print(f"  VAR9统计：最大值={df['VAR9'].max():.4f}, 平均值={df['VAR9'].mean():.4f}, 最后10行：{df['VAR9'].tail(10).tolist()}")
    
    # 调试信息已在上面的VAR8计算对比中显示，这里不再重复
    
    # 调试信息：检查19号前后的VAR8序列（用于验证VAR8计算）
    print(f"\n  调试信息 - 19号前后的VAR8序列（用于验证VAR8计算）：")
    check_date_str = '2025-12-19'
    if check_date_str in df['date'].values:
        check_idx = df[df['date'] == check_date_str].index[0]
        # 显示19号前后各5天的数据
        start_idx = max(0, check_idx - 5)
        end_idx = min(len(df), check_idx + 6)
        print(f"    日期范围：{df.iloc[start_idx]['date']} 至 {df.iloc[end_idx-1]['date']}")
        for i in range(start_idx, end_idx):
            date_val = df.iloc[i]['date']
            close_val = df.iloc[i]['close']
            low_val = df.iloc[i]['low']
            high_val = df.iloc[i]['high']
            llv_21 = df.iloc[i]['llv_l21']
            hhv_21 = df.iloc[i]['hhv_h21']
            var8_val = df.iloc[i]['VAR8']
            marker = " <-- 19号" if date_val == check_date_str else ""
            print(f"      [{i}] {date_val}: close={close_val:.2f}, low={low_val:.2f}, high={high_val:.2f}, "
                  f"LLV21={llv_21:.2f}, HHV21={hhv_21:.2f}, VAR8={var8_val:.4f}{marker}")
    
    # 风险:=CEILING(SMA(VAR9,13,8))
    # 根据原始公式：风险 = CEILING(SMA(VAR9, 13, 8))
    # 严格按照公式计算，SMA函数会自然处理NaN值
    df['风险_temp'] = sma(df['VAR9'], 13, 8)
    
    print(f"  风险_temp（SMA(VAR9,13,8)）统计：最大值={df['风险_temp'].max():.4f}, 平均值={df['风险_temp'].mean():.4f}, 最后10行：{df['风险_temp'].tail(10).tolist()}")
    
    # 手动验证19号的SMA计算（用于调试）
    check_date_str = '2025-12-19'
    if check_date_str in df['date'].values:
        check_idx = df[df['date'] == check_date_str].index[0]
        if check_idx >= 13:  # 确保有足够的历史数据
            print(f"\n  手动验证19号的SMA计算（SMA(VAR9,13,8)）：")
            var9_val = df.iloc[check_idx]['VAR9']
            risk_temp_val = df.iloc[check_idx]['风险_temp']
            print(f"    19号的VAR9={var9_val:.4f} (NaN: {pd.isna(var9_val)})")
            print(f"    19号的风险_temp={risk_temp_val:.4f} (NaN: {pd.isna(risk_temp_val)})")
            # 手动计算：SMA(x,13,8) = (8*x + 5*SMA_prev) / 13
            if not pd.isna(risk_temp_val):
                prev_risk_temp = df.iloc[check_idx-1]['风险_temp']
                if pd.isna(prev_risk_temp):
                    print(f"    警告：前一个风险_temp是NaN，无法手动验证")
                elif pd.isna(var9_val):
                    print(f"    警告：VAR9是NaN，无法手动验证")
                else:
                    manual_calc = (8 * var9_val + 5 * prev_risk_temp) / 13
                    print(f"    手动计算：风险_temp = (8*{var9_val:.4f} + 5*{prev_risk_temp:.4f}) / 13 = {manual_calc:.4f}")
                    print(f"    实际值：{risk_temp_val:.4f}, 差异：{abs(manual_calc - risk_temp_val):.6f}")
    
    # 调试信息：检查19号前后的VAR9和风险_temp序列（用于验证SMA计算）
    print(f"\n  调试信息 - 19号前后的VAR9和风险_temp序列（用于验证SMA计算）：")
    check_date_str = '2025-12-19'
    if check_date_str in df['date'].values:
        check_idx = df[df['date'] == check_date_str].index[0]
        # 显示19号前后各5天的数据
        start_idx = max(0, check_idx - 5)
        end_idx = min(len(df), check_idx + 6)
        print(f"    日期范围：{df.iloc[start_idx]['date']} 至 {df.iloc[end_idx-1]['date']}")
        for i in range(start_idx, end_idx):
            date_val = df.iloc[i]['date']
            var9_val = df.iloc[i]['VAR9']
            risk_temp_val = df.iloc[i]['风险_temp']
            marker = " <-- 19号" if date_val == check_date_str else ""
            print(f"      [{i}] {date_val}: VAR9={var9_val:.4f}, 风险_temp={risk_temp_val:.4f}{marker}")
    
    # 最终指标
    df['底线'] = 0  # 固定值0
    df['主力吸货'] = df['VAR7']
    
    # CEILING向上取整，并转换为整数类型
    # 注意：通达信的CEILING函数是向上取整
    # 对于NaN值，CEILING后仍然是NaN，需要处理
    df['风险'] = np.ceil(df['风险_temp']).astype(float)  # 先转为float以保留NaN
    # 将NaN转换为0（或者保持NaN，根据需求）
    df['风险'] = df['风险'].fillna(0).astype(int)  # 填充NaN为0后转为整数
    
    print(f"  风险（CEILING后）统计：最大值={df['风险'].max()}, 平均值={df['风险'].mean():.2f}, 最后10行：{df['风险'].tail(10).tolist()}")
    
    # 对比检查：显示风险_temp和风险的对应关系（最后5行）
    print(f"\n  风险值对比（最后5行）：")
    for i in range(-5, 0):
        idx = len(df) + i
        date_val = df.iloc[idx]['date']
        risk_temp_val = df['风险_temp'].iloc[idx]
        risk_val = df['风险'].iloc[idx]
        ceil_val = np.ceil(risk_temp_val)
        print(f"    [{idx}] {date_val}: 风险_temp={risk_temp_val:.4f} -> CEILING={ceil_val:.0f} -> 风险={risk_val}")
    
    # 详细验证18号和19号的风险值计算
    print(f"\n  详细验证18号和19号的风险值计算：")
    check_dates = ['2025-12-18', '2025-12-19']
    for check_date in check_dates:
        if check_date in df['date'].values:
            check_idx = df[df['date'] == check_date].index[0]
            row = df.iloc[check_idx]
            var8_val = row['VAR8']
            var9_val = row['VAR9']
            risk_temp_val = row['风险_temp']
            risk_val = row['风险']
            
            # 计算CEILING值
            if pd.isna(risk_temp_val):
                ceil_val = np.nan
            else:
                ceil_val = np.ceil(risk_temp_val)
            
            print(f"    {check_date} (索引{check_idx}):")
            print(f"      VAR8={var8_val:.4f} (NaN: {pd.isna(var8_val)})")
            print(f"      VAR9={var9_val:.4f} (NaN: {pd.isna(var9_val)})")
            print(f"      风险_temp={risk_temp_val:.4f} (NaN: {pd.isna(risk_temp_val)})")
            if pd.isna(ceil_val):
                print(f"      CEILING(风险_temp)=NaN, 风险={risk_val}")
            else:
                print(f"      CEILING(风险_temp)={ceil_val:.0f}, 风险={risk_val}")
    # 涨跌指标：MA(3*SMA(...) - 2*SMA(SMA(...)),5)
    # 原始公式：MA(3*SMA((C-LLV(L,27))/(HHV(H,27)-LLV(L,27))*100,5,1)-2*SMA(SMA((C-LLV(L,27))/(HHV(H,27)-LLV(L,27))*100,5,1),3,1),5)
    llv_27 = df['low'].rolling(27).min()
    hhv_27 = df['high'].rolling(27).max()
    denominator = hhv_27 - llv_27
    # 处理除零情况
    temp1_value = np.where(denominator != 0,
                           (df['close'] - llv_27) / denominator * 100,
                           0)
    temp1_series = pd.Series(temp1_value, index=df.index)
    temp1_series = temp1_series.fillna(0)  # 填充NaN为0
    temp1 = sma(temp1_series, 5, 1)
    temp1 = temp1.fillna(0)  # 填充SMA计算产生的NaN
    temp2 = sma(temp1, 3, 1)
    temp2 = temp2.fillna(0)  # 填充SMA计算产生的NaN
    # 注意：原始公式用的是MA（简单移动平均），不是EMA
    temp_diff = 3*temp1 - 2*temp2
    temp_diff = temp_diff.fillna(0)  # 填充NaN
    df['涨跌'] = ma(temp_diff, 5)
    df['涨跌'] = df['涨跌'].fillna(0)  # 最终填充NaN

    return df

def plot_indicator(df):
    """
    可视化指标结果
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
    
    # 子图1：收盘价 + 涨跌线
    ax1.plot(df['date'], df['close'], label='收盘价', color='black', linewidth=1)
    ax1.plot(df['date'], df['涨跌'], label='涨跌', color='red', linewidth=2)
    ax1.set_ylabel('价格/涨跌值')
    ax1.legend()
    ax1.grid(True)
    
    # 子图2：主力吸货 + 风险线 + 底线
    ax2.plot(df['date'], df['底线'], label='底线', color='cyan', linewidth=1)
    ax2.plot(df['date'], df['主力吸货'], label='主力吸货', color='blue', linewidth=2)
    ax2.plot(df['date'], df['风险'], label='风险', color='green', linewidth=2)
    # 绘制吸筹彩色柱（模拟通达信STICKLINE）
    ax2.bar(df['date'], df['主力吸货'], color='magenta', alpha=0.5, label='吸筹柱')
    ax2.set_ylabel('指标值')
    ax2.set_xlabel('日期')
    ax2.legend()
    ax2.grid(True)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# ========== 主程序运行 ==========
if __name__ == "__main__":
    # 配置参数（需根据你的本地通达信路径修改）
    stock_code = "600519"  # 贵州茅台
    tdx_data_path = "E:/new_tdx"  # 通达信根目录（mootdx需要根目录，如 "E:/new_tdx"，不是vipdoc子目录）
    start_date = "2025-11-01"  # 筛选开始日期
    end_date = "2025-12-28"    # 筛选结束日期
    
    # 执行流程
    try:
        # 1. 读取本地数据（包含足够的历史数据用于计算）
        stock_df = get_local_stock_data(stock_code, tdx_data_path, start_date, end_date)
        
        # 2. 计算指标（使用全部历史数据）
        print(f"\n计算指标前，数据量：{len(stock_df)}条，日期范围：{stock_df['date'].min()} 至 {stock_df['date'].max()}")
        indicator_df = calculate_stock_indicator(stock_df)
        print(f"计算指标后，数据量：{len(indicator_df)}条，日期范围：{indicator_df['date'].min()} 至 {indicator_df['date'].max()}")
        
        # 3. 按日期筛选最终结果（只显示指定日期范围的数据）
        if start_date:
            indicator_df = indicator_df[indicator_df['date'] >= start_date]
        if end_date:
            indicator_df = indicator_df[indicator_df['date'] <= end_date]
        print(f"筛选后，数据量：{len(indicator_df)}条，日期范围：{indicator_df['date'].min()} 至 {indicator_df['date'].max()}")
        
        # 重置索引
        indicator_df.reset_index(drop=True, inplace=True)
        
        # 4. 输出结果
        print(f"\n指标计算结果（筛选后共{len(indicator_df)}条，日期范围：{indicator_df['date'].min()} 至 {indicator_df['date'].max()}）：")
        # 格式化输出，主力吸货保留2位小数
        output_df = indicator_df[['date', 'close', '主力吸货', '风险', '涨跌']].copy()
        output_df['主力吸货'] = output_df['主力吸货'].round(2)
        print(output_df)
        
        # 调试信息：检查19号及之后的风险值（在计算时的原始数据中查找）
        print(f"\n调试信息 - 19号及之后的风险值详细检查（计算时的原始数据）：")
        # 使用保存的原始计算结果
        if 'original_indicator_df' in locals():
            check_dates = ['2025-12-19', '2025-12-22', '2025-12-23', '2025-12-24', '2025-12-26']
            for check_date in check_dates:
                mask = original_indicator_df['date'] == check_date
                if mask.any():
                    idx = original_indicator_df[mask].index[0]
                    row = original_indicator_df.loc[idx]
                    print(f"  {check_date} (索引{idx}): 风险={row['风险']}, 风险_temp={row['风险_temp']:.4f}, "
                          f"VAR9={row['VAR9']:.4f}, VAR8={row['VAR8']:.4f}, "
                          f"close={row['close']:.2f}, low={row['low']:.2f}, high={row['high']:.2f}")
                else:
                    print(f"  {check_date}: 在原始数据中未找到该日期")
        
        # 同时在筛选后的数据中检查
        print(f"\n调试信息 - 19号及之后的风险值详细检查（筛选后的数据）：")
        check_dates = ['2025-12-19', '2025-12-22', '2025-12-23', '2025-12-24', '2025-12-26']
        for check_date in check_dates:
            mask = indicator_df['date'] == check_date
            if mask.any():
                idx = indicator_df[mask].index[0]
                row = indicator_df.loc[idx]
                risk_temp_val = f"{row['风险_temp']:.4f}" if '风险_temp' in indicator_df.columns else 'N/A'
                var9_val = f"{row['VAR9']:.4f}" if 'VAR9' in indicator_df.columns else 'N/A'
                var8_val = f"{row['VAR8']:.4f}" if 'VAR8' in indicator_df.columns else 'N/A'
                print(f"  {check_date}: 风险={row['风险']}, 风险_temp={risk_temp_val}, VAR9={var9_val}, VAR8={var8_val}")
            else:
                print(f"  {check_date}: 数据中未找到该日期")
        
        # 调试信息：显示中间变量（如果存在）
        if 'VAR6' in indicator_df.columns:
            print(f"\n调试信息 - VAR6（创90日新低标志）统计：")
            print(f"  VAR6=1的数量：{(indicator_df['VAR6']==1).sum()}")
            print(f"  VAR6=0的数量：{(indicator_df['VAR6']==0).sum()}")
            if 'var7_ema' in indicator_df.columns:
                print(f"\n调试信息 - VAR7计算过程：")
                print(f"  var7_ema（EMA部分）最大值：{indicator_df['var7_ema'].max():.4f}")
                print(f"  var7_ema（EMA部分）平均值：{indicator_df['var7_ema'].mean():.4f}")
                print(f"  VAR7（最终值）最大值：{indicator_df['VAR7'].max():.4f}")
                print(f"  注意：VAR7 = var7_ema / 618 * VAR6，如果VAR6全为0，则VAR7全为0")
        
        # 5. 可视化
        # plot_indicator(indicator_df)
        
    except Exception as e:
        print(f"程序运行出错：{e}")
        import traceback
        traceback.print_exc()