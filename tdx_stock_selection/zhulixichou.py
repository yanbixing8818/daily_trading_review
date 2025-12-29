from mootdx.reader import Reader
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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
    
    def sma(x, n, m=1):
        """通达信SMA函数：SMA(x, n, m) = (m*x + (n-m)*SMA_prev) / n"""
        if not isinstance(x, pd.Series):
            x = pd.Series(x)
        result = pd.Series(index=x.index, dtype=float)
        
        first_valid_idx = x.first_valid_index()
        if first_valid_idx is None:
            return result
        
        first_valid_pos = x.index.get_loc(first_valid_idx)
        result.iloc[first_valid_pos] = x.iloc[first_valid_pos]
        
        for i in range(first_valid_pos + 1, len(x)):
            prev_sma = result.iloc[i-1]
            if pd.isna(prev_sma) or pd.isna(x.iloc[i]):
                result.iloc[i] = np.nan
            else:
                result.iloc[i] = (m * x.iloc[i] + (n - m) * prev_sma) / n
        
        return result
    
    def ema(x, n):
        """指数移动平均"""
        if not isinstance(x, pd.Series):
            if isinstance(x, np.ndarray):
                x = pd.Series(x, index=df.index)
            else:
                x = pd.Series(x)
        return x.ewm(span=n, adjust=False).mean()
    
    def ma(x, n):
        """简单移动平均"""
        return x.rolling(window=n).mean()
    
    # VAR1:=REF(LOW,1)
    df['VAR1'] = df['low'].shift(1)
    
    # VAR2:=SMA(ABS(LOW-VAR1),3,1)/SMA(MAX(LOW-VAR1,0),3,1)*100
    df['abs_low_var1'] = np.abs(df['low'] - df['VAR1'])
    df['max_low_var1'] = np.maximum(df['low'] - df['VAR1'], 0)
    sma_abs = sma(df['abs_low_var1'], 3, 1)
    sma_max = sma(df['max_low_var1'], 3, 1)
    df['VAR2'] = np.where(sma_max != 0, sma_abs / sma_max * 100, 0)
    df['VAR2'] = df['VAR2'].fillna(0)
    
    # VAR3:=EMA(IF(CLOSE*1.2,VAR2*10,VAR2/10),3)
    var3_condition = pd.Series(np.where(df['close'] * 1.2 != 0, df['VAR2']*10, df['VAR2']/10), index=df.index)
    df['VAR3'] = ema(var3_condition, 3)
    
    # VAR4:=LLV(LOW,38)  # 38日最低价的最低值
    df['VAR4'] = df['low'].rolling(window=38).min()
    
    # VAR5:=HHV(VAR3,38)  # 38日VAR3的最高值
    df['VAR5'] = df['VAR3'].rolling(window=38).max()
    
    # VAR6:=IF(LLV(LOW,90),1,0)
    df['llv_low_90'] = df['low'].rolling(window=90).min()
    df['VAR6'] = np.where((df['llv_low_90'].notna()) & (df['llv_low_90'] != 0), 1, 0)
    
    # VAR7:=EMA(IF(LOW<=VAR4,(VAR3+VAR5*2)/2,0),3)/618*VAR6
    df['var7_temp'] = pd.Series(np.where(df['low'] <= df['VAR4'], (df['VAR3'] + df['VAR5']*2)/2, 0), index=df.index)
    df['var7_temp'] = df['var7_temp'].fillna(0)
    df['var7_ema'] = ema(df['var7_temp'], 3)
    df['VAR7'] = df['var7_ema'] / 618 * df['VAR6']
    df['VAR7'] = df['VAR7'].fillna(0)
    
    # VAR8:=((C-LLV(L,21))/(HHV(H,21)-LLV(L,21)))*100
    df['llv_l21'] = df['low'].rolling(window=21, min_periods=1).min()
    df['hhv_h21'] = df['high'].rolling(window=21, min_periods=1).max()
    df['VAR8'] = (df['close'] - df['llv_l21']) / (df['hhv_h21'] - df['llv_l21']) * 100
    df['VAR8'] = df['VAR8'].replace([np.inf, -np.inf], 0).fillna(0)
    
    # VAR9:=SMA(VAR8,13,8)
    df['VAR9'] = sma(df['VAR8'], 13, 8)
    
    # 风险:=CEILING(SMA(VAR9,13,8))
    df['风险_temp'] = sma(df['VAR9'], 13, 8)
    df['风险'] = np.ceil(df['风险_temp']).astype(float).fillna(0).astype(int)
    
    # 最终指标
    df['底线'] = 0
    df['主力吸货'] = df['VAR7']
    # 涨跌指标：MA(3*SMA(...) - 2*SMA(SMA(...)),5)
    llv_27 = df['low'].rolling(27).min()
    hhv_27 = df['high'].rolling(27).max()
    denominator = hhv_27 - llv_27
    temp1_value = np.where(denominator != 0, (df['close'] - llv_27) / denominator * 100, 0)
    temp1_series = pd.Series(temp1_value, index=df.index).fillna(0)
    temp1 = sma(temp1_series, 5, 1).fillna(0)
    temp2 = sma(temp1, 3, 1).fillna(0)
    temp_diff = 3*temp1 - 2*temp2
    df['涨跌'] = ma(temp_diff, 5).fillna(0)

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
    stock_code = "600519"
    tdx_data_path = "E:/new_tdx"
    start_date = "2025-11-01"
    end_date = "2025-12-28"
    
    try:
        stock_df = get_local_stock_data(stock_code, tdx_data_path, start_date, end_date)
        indicator_df = calculate_stock_indicator(stock_df)
        
        if start_date:
            indicator_df = indicator_df[indicator_df['date'] >= start_date]
        if end_date:
            indicator_df = indicator_df[indicator_df['date'] <= end_date]
        
        indicator_df.reset_index(drop=True, inplace=True)
        
        print(f"\n指标计算结果（筛选后共{len(indicator_df)}条）：")
        output_df = indicator_df[['date', 'close', '主力吸货', '风险', '涨跌']].copy()
        output_df['主力吸货'] = output_df['主力吸货'].round(2)
        print(output_df)
        
    except Exception as e:
        print(f"程序运行出错：{e}")
        import traceback
        traceback.print_exc()