# 该选股思路，参考中科海迅2025年06月27日结果和新城市20250704和20250708结果
# 思路：
# 1. 检查目标日是否接近一年新高，且收盘价在一年高点的80%以上
# 2. 检查目标日是否有放量上影线，且上影线长度大于实体长度
# 3. 检查均线趋势：多头排列且向上发散
# 4. 检查MACD和RSI：MACD金叉且RSI处于强势区

#下面是该代码还未实现的思路：
# 5. 圆弧底，底部筹码要干净；
# 6. 市值要小，最好小于50亿，该选股思路适用于龙头股做短线投机，不适合基本面投资。

# 使用方法：
# 可以填写name_map = {'300810': '中科海迅', '300778': '新城市'}，这样就可以使用中科海迅和新城市来debug了
# 注释掉name_map = {'300810': '中科海迅', '300778': '新城市'}，这样就可以使用全市场股票来选股了
# 后续日期最好通过函数参数来指定，这样就可以选出不同日期的股票了，方便回测。


import os
import pandas as pd
import numpy as np
import talib
from mootdx.reader import Reader
from datetime import datetime, timedelta
import logging
import sys
from mootdx.quotes import Quotes

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StockSelector')

class StockSelector:
    def __init__(self, tdx_path='E:/new_tdx'):
        """
        初始化选股器
        :param tdx_path: 通达信数据目录路径
        """
        self.reader = Reader.factory(market='std', tdxdir=tdx_path)
        self.today = datetime.now().date()
        self.start_date = (self.today - timedelta(days=400)).strftime('%Y-%m-%d')
        self.end_date = self.today.strftime('%Y-%m-%d')
        
    def get_stock_codes(self):
        # 兼容旧逻辑优先
        name_map = {
            # '300810': '中科海迅',
            # '300778': '新城市'
        }
        if name_map:
            self.code_name_map = name_map
            return list(name_map.keys())
        # 否则走 akshare 全A股
        import akshare as ak
        stock_df = ak.stock_info_a_code_name()
        codes = stock_df['code'].tolist()
        self.code_name_map = dict(zip(stock_df['code'], stock_df['name']))
        return codes
    
    def get_stock_name(self, code):
        """获取股票名称，优先用映射表"""
        if hasattr(self, 'code_name_map'):
            return self.code_name_map.get(code, f"股票{code}")
        # 兼容旧逻辑
        name_map = {
            '300810': '中科海迅',
            '300778': '新城市'
            # '600519': '贵州茅台',
            # '000858': '五粮液',
            # '601318': '中国平安'
        }
        return name_map.get(code, f"股票{code}")
    
    def load_stock_data(self, code):
        try:
            df = self.reader.daily(symbol=code)
            if df is None or df.empty:
                logger.warning(f"{code}数据为空")
                return None
            
            # 检查数据列是否包含日期字段
            if 'date' not in df.columns and not df.empty:
                # 尝试从索引中恢复日期（mootdx常见数据格式）
                if df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()  # 将索引转为列
                # 特殊处理：某些版本返回'日期'中文列名
                elif '日期' in df.columns:
                    df = df.rename(columns={'日期': 'date'})
            
            # 验证日期字段是否存在
            if 'date' not in df.columns:
                logger.error(f"{code}数据缺少日期列，现有列：{list(df.columns)}")
                return None
                
            # 转换日期格式（添加错误处理）
            try:
                df['date'] = pd.to_datetime(df['date'])
            except Exception as e:
                logger.error(f"{code}日期转换失败: {str(e)}")
                # 尝试解析常见日期格式
                try:
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')  # 处理20250711格式
                except:
                    return None
            
            # 筛选日期范围（添加空值过滤）
            df = df.sort_values('date').dropna(subset=['date'])
            df = df[(df['date'] >= self.start_date) & (df['date'] <= self.end_date)]
            return df
        
        except Exception as e:
            logger.error(f"加载{code}数据失败: {str(e)}", exc_info=True)
            return None
    
    def calculate_technical_indicators(self, df):
        """
        使用TA-Lib计算所有技术指标
        :param df: 股票数据DataFrame
        :return: 添加技术指标后的DataFrame
        """

        # 新增：检查数据列完整性
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.error("数据缺失必要列！")
            return None
            
        # 新增：检查数据量是否足够（动态计算所需最小数据量）
        min_days = 252  # 至少需 252 天，但 MACD 需额外冗余
        print(len(df))
        if len(df) < min_days:
            logger.warning(f"数据不足{min_days}天，无法计算指标")
            return None
            
        # 转换数据类型为TA-Lib所需格式
        df = df.copy()
        close = df['close'].values.astype(np.float64)
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        open = df['open'].values.astype(np.float64)
        volume = df['volume'].values.astype(np.float64)
        
        # 1. 计算移动平均线（使用TA-Lib）
        df['MA5'] = talib.SMA(close, timeperiod=5)
        df['MA10'] = talib.SMA(close, timeperiod=10)
        df['MA20'] = talib.SMA(close, timeperiod=20)
        df['MA60'] = talib.SMA(close, timeperiod=60)
        
        # 2. 计算一年新高（252交易日）[2](@ref)
        period = min(252, len(df))
        df['year_high'] = talib.MAX(high, timeperiod=period)
        print(f"[DEBUG] {df['date'].iloc[0]}~{df['date'].iloc[-1]} 共{len(df)}天")
        print(f"[DEBUG] high head: {df['high'].head().to_list()}")
        print(f"[DEBUG] year_high head: {df['year_high'].head(10).to_list()}")
        print(f"[DEBUG] year_high tail: {df['year_high'].tail(10).to_list()}")
        print(f"[DEBUG] year_high NaN数: {df['year_high'].isna().sum()}")
        df['close_to_high'] = df['close'] / df['year_high']
        
        # 3. 计算K线形态（上影线和实体长度）
        df['upper_shadow'] = df['high'] - np.maximum(df['close'], df['open'])
        df['body'] = np.abs(df['close'] - df['open'])
        
        # 4. 计算MACD和RSI用于趋势验证[5,7](@ref)
        df['MACD'], df['MACD_signal'], _ = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        df['RSI'] = talib.RSI(close, timeperiod=14)
        
        # 5. 计算均线斜率（角度）
        def calculate_slope(series):
            """计算均线斜率（角度）"""
            if len(series) < 2:
                return 0
            dy = series.iloc[-1] - series.iloc[-2]
            return np.degrees(np.arctan(dy))
            
        df['MA5_slope'] = df['MA5'].rolling(window=2).apply(calculate_slope, raw=False)
        df['MA10_slope'] = df['MA10'].rolling(window=2).apply(calculate_slope, raw=False)
        
        # 处理初始NaN值
        return df.dropna(subset=['MA60'])
    
    def check_near_year_high(self, df):
        """
        检查目标日是否接近一年新高[3](@ref)
        :param df: 股票数据DataFrame
        :return: bool
        """
        if len(df) == 0:
            return False
        val = df['close_to_high'].iloc[-1]
        print(f"[DEBUG] check_near_year_high target close_to_high: {val}")
        return val >= 0.80
    
    def check_volume_shadow(self, df):
        """
        检查目标日是否有放量上影线
        :param df: 股票数据DataFrame
        :return: bool
        """
        if len(df) < 2:
            return False
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        # 条件：成交量放大（>前一日1.5倍）且上影线较长（>实体长度）
        print(f"[DEBUG] check_volume_shadow today volume: {today['volume']}, yesterday volume: {yesterday['volume']}, upper_shadow: {today['upper_shadow']}, body: {today['body']}")
        print(f"[DEBUG] 放量阈值: {yesterday['volume']*1.3}, 实际: {today['volume']}")
        return today['volume'] > yesterday['volume'] * 1.3 and today['upper_shadow'] > today['body']
    
    def check_ma_trend(self, df):
        """
        检查均线趋势：多头排列且向上发散[4,7](@ref)
        :param df: 股票数据DataFrame
        :return: bool
        """
        if len(df) < 60:
            print(f"[DEBUG] 均线趋势: 数据不足60天，实际{len(df)}天")
            return False

        last_row = df.iloc[-1]
        ma_condition = (
            last_row['MA5'] > last_row['MA10'] and 
            last_row['MA10'] > last_row['MA20'] and 
            last_row['MA20'] > last_row['MA60']
        )
        print(f"[DEBUG] 均线多头排列: MA5={last_row['MA5']}, MA10={last_row['MA10']}, MA20={last_row['MA20']}, MA60={last_row['MA60']} -> {ma_condition}")

        slope_condition = last_row['MA5_slope'] > 10 and last_row['MA10_slope'] > 10
        print(f"[DEBUG] 均线斜率: MA5_slope={last_row['MA5_slope']}, MA10_slope={last_row['MA10_slope']} -> {slope_condition}")

        trend_strength = (
            last_row['MACD'] > last_row['MACD_signal'] and
            last_row['RSI'] > 50
        )
        print(f"[DEBUG] 趋势强度: MACD={last_row['MACD']}, MACD_signal={last_row['MACD_signal']}, RSI={last_row['RSI']} -> {trend_strength}")

        return ma_condition and slope_condition and trend_strength
    
    def select_stocks(self, target_date=None):
        """执行选股流程"""
        selected_stocks = []
        codes = self.get_stock_codes()
        
        logger.info(f"开始选股，共{len(codes)}只股票待筛选...")
        
        for code in codes:
            try:
                name = self.get_stock_name(code)
                logger.info(f"分析中: {name}({code})")
                
                # 1. 加载数据
                df = self.load_stock_data(code)
                if df is None or len(df) < 252:
                    logger.warning(f"{name}数据不足252天，跳过分析")
                    continue
                
                # 2. 计算技术指标
                df = self.calculate_technical_indicators(df)
                if df is None:
                    logger.warning(f"{name}技术指标计算失败")
                    continue

                # 只判断目标日
                if target_date is not None:
                    # 转换为datetime.date
                    if isinstance(target_date, str):
                        target_date_dt = pd.to_datetime(target_date).date()
                    elif isinstance(target_date, pd.Timestamp):
                        target_date_dt = target_date.date()
                    elif isinstance(target_date, (datetime,)):
                        target_date_dt = target_date.date()
                    else:
                        target_date_dt = target_date
                    df_on_date = df[df['date'].dt.date == target_date_dt]
                    if df_on_date.empty:
                        logger.warning(f"{name}在{target_date}无数据，跳过")
                        continue
                    df_on_date = df_on_date.copy()
                    df_on_date['code'] = code  # 增加code列
                    print(f"\n[DEBUG] {name}({code}) {target_date} 数据:\n{df_on_date}")
                    # 保存当天数据到csv，便于debug
                    debug_csv = f"debug_{target_date}_data.csv"
                    if not os.path.exists(debug_csv):
                        df_on_date.to_csv(debug_csv, index=False, mode='w', encoding='utf-8-sig')
                    else:
                        df_on_date.to_csv(debug_csv, index=False, mode='a', header=False, encoding='utf-8-sig')
                    # 保留目标日及之前所有数据（不少于60天，建议252天）
                    df = df[df['date'] <= pd.to_datetime(target_date_dt)]
                    if len(df) < 60:
                        logger.warning(f"{name}在{target_date}及之前不足60天，跳过")
                        continue

                # 3. 检查选股条件
                condition1 = self.check_near_year_high(df)
                condition2 = self.check_volume_shadow(df)
                condition3 = self.check_ma_trend(df)
                
                logger.info(f"{name}条件检查: 近一年新高={condition1}, 放量上影线={condition2}, 均线趋势={condition3}")
                
                if condition1 and condition2 and condition3:
                    last_close = df['close'].iloc[-1]
                    year_high = df['year_high'].iloc[-1]
                    close_ratio = last_close / year_high
                    
                    selected_stocks.append({
                        'code': code,
                        'name': name,
                        '最新价': last_close,
                        '一年新高': year_high,
                        '接近度': f"{close_ratio:.2%}",
                        'MA5': df['MA5'].iloc[-1],
                        'MA10': df['MA10'].iloc[-1],
                        'MA5斜率': df['MA5_slope'].iloc[-1],
                        'MA10斜率': df['MA10_slope'].iloc[-1],
                        'MACD': df['MACD'].iloc[-1],
                        'RSI': df['RSI'].iloc[-1]
                    })
                    
            except Exception as e:
                logger.error(f"处理{code}失败: {str(e)}")
        
        # 转换为DataFrame并保存结果
        if selected_stocks:
            result_df = pd.DataFrame(selected_stocks)
            result_df = result_df.sort_values('接近度', ascending=False)
            output_file = f"selected_stocks_{self.today.strftime('%Y%m%d')}.csv"
            result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
            logger.info(f"选股完成! 共选出{len(selected_stocks)}只股票，结果已保存到: {output_file}")
            return result_df
        else:
            logger.info("未选出符合所有条件的股票")
            return pd.DataFrame()

if __name__ == "__main__":
    selector = StockSelector(tdx_path="E:/new_tdx")  # 修改为您的通达信数据目录
    # 可指定target_date，如 '2023-01-01'，否则为最近一天
    result = selector.select_stocks(target_date='2025-07-14')
    # result = selector.select_stocks()
    
    if not result.empty:
        print("\n===== 选股结果 =====")
        print(result[['code', 'name', '最新价', '一年新高', '接近度']])
