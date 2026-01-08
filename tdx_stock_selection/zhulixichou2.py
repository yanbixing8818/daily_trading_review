import pandas as pd
import numpy as np
from mootdx.reader import Reader
from mootdx.quotes import Quotes
import logging

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    import MyTT as mt
except ImportError as e:
    raise ImportError(
        "未找到 MyTT 库，请先安装后再使用本模块：\n"
        "    pip install MyTT\n"
        f"原始错误：{e}"
    )

# 复用老文件中的股票列表/名称映射工具，避免重复实现
try:
    from tdx_stock_selection.zhulixichou import get_all_stock_codes, get_stock_name_map
except Exception:
    # 兼容直接运行本文件时的相对导入
    try:
        from zhulixichou import get_all_stock_codes, get_stock_name_map
    except Exception:
        get_all_stock_codes = None
        get_stock_name_map = None


def _get_series(df: pd.DataFrame, *candidates):
    """
    从 DataFrame 中按多个候选列名依次查找，返回第一个存在的列（作为 Series）。
    """
    for name in candidates:
        if name in df.columns:
            return df[name]
    raise KeyError(f"在 DataFrame 中未找到任一列：{candidates}")


def _WINNER(close: pd.Series, period: int = 60) -> pd.Series:
    """
    计算获利比例（WINNER函数的简化实现）。
    
    通达信WINNER(CLOSE)返回当前价格下获利盘的比例。
    这里使用简化算法：基于价格在近期价格区间中的位置来估算。
    
    参数
    ----
    close : pd.Series
        收盘价序列
    period : int
        用于计算价格区间的周期，默认60日
    
    返回
    ----
    pd.Series
        获利比例（0-1之间的小数）
    """
    # 计算近期最低价和最高价
    low_min = close.rolling(window=period, min_periods=1).min()
    high_max = close.rolling(window=period, min_periods=1).max()
    
    # 价格区间
    price_range = high_max - low_min
    
    # 避免除零
    price_range = price_range.replace(0, np.nan)
    
    # 计算当前价格相对于最低价的位置
    # 如果当前价格接近最高价，获利比例高；接近最低价，获利比例低
    position = (close - low_min) / price_range
    
    # 限制在0-1之间
    position = position.clip(0, 1)
    
    return position.fillna(0.5)  # 如果无法计算，默认50%


def _COST(close: pd.Series, vol: pd.Series, percent: float, period: int = 60) -> pd.Series:
    """
    计算成本分布函数（COST函数的简化实现）。
    
    通达信COST(percent)返回获利盘为percent%时的价格。
    这里使用简化算法：基于成交量加权价格分布来估算。
    
    参数
    ----
    close : pd.Series
        收盘价序列
    vol : pd.Series
        成交量序列
    percent : float
        百分比（0-100之间）
    period : int
        用于计算成本分布的周期，默认60日
    
    返回
    ----
    pd.Series
        对应百分位的成本价格
    """
    # 使用滚动窗口计算成交量加权平均价格（VWAP）作为成本基准
    vwap = (close * vol).rolling(window=period, min_periods=1).sum() / vol.rolling(window=period, min_periods=1).sum()
    
    # 计算价格的标准差来衡量价格分布
    price_std = close.rolling(window=period, min_periods=1).std()
    
    # 计算价格区间
    low_min = close.rolling(window=period, min_periods=1).min()
    high_max = close.rolling(window=period, min_periods=1).max()
    price_range = high_max - low_min
    
    # 简化方法：基于价格区间和percent计算成本价格
    # percent=5时接近最低价，percent=95时接近最高价
    # 线性插值：cost = low + (high - low) * (percent / 100)
    # 但考虑VWAP作为中心，进行偏移调整
    cost_price = low_min + (high_max - low_min) * (percent / 100.0)
    
    # 结合VWAP进行调整：如果percent<50，偏向低价；percent>50，偏向高价
    adjustment = (percent - 50) / 50.0 * price_std.fillna(0) * 0.5
    cost_price = cost_price + adjustment
    
    return cost_price.fillna(close)  # 如果无法计算，使用收盘价


def calculate_selection_signals(
    df: pd.DataFrame,
    n1: int = 90,
    n2: int = 10,
    min_marketcap: float = 80,
) -> pd.DataFrame:
    """
    仿照通达信公式，将以下选股逻辑转为 Python（基于 MyTT 库）：
    【已注释掉市值条件相关逻辑】

        N1:=90;
        N2:=10;
        MIN_MARKETCAP:=80;
        WinRatio:=WINNER(CLOSE)*100;
        CostConcentration:=(COST(95)-COST(5))/(COST(95)+COST(5))*100;
        CircMarketCap:=FINANCE(40)/10000*CLOSE;
        TotalMarketCap:=FINANCE(1)/10000*CLOSE;
        Condition1:=WinRatio<N1;
        Condition2:=CostConcentration<N2;
        Condition3:=COUNT(CostConcentration<N2,30)>=15;
        # MarketCapCondition:=TotalMarketCap>=MIN_MARKETCAP; 【已注释】
        LowPriceZone:=CLOSE/HHV(HIGH,120)<0.7;
        # Selection:Condition1 AND Condition2 AND Condition3 AND MarketCapCondition AND LowPriceZone; 【已修改】
        Selection:Condition1 AND Condition2 AND Condition3 AND LowPriceZone;
        VOL_MA5:=MA(VOL,5);
        VOL_MA20:=MA(VOL,20);
        VolumeActive:=VOL_MA5>VOL_MA20;

    参数
    ----
    df : pd.DataFrame
        需要至少包含以下列（大小写任意，其一即可）：
        - 收盘价: 'close' 或 'CLOSE'
        - 最高价: 'high' 或 'HIGH'
        - 成交量: 'vol' 或 'VOL'
        - 财务数据: FINANCE(1) 与 FINANCE(40) 对应列，例如：
            'FINANCE_1', 'finance_1', 'FINANCE1', 'finance1'
            'FINANCE_40', 'finance_40', 'FINANCE40', 'finance40'
        其中 FINANCE(1)/FINANCE(40) 单位需为“万股”，以便与公式一致：
            市值(亿元) = FINANCE(x) / 10000 * CLOSE

    返回
    ----
    pd.DataFrame
        在原 df 基础上增加以下列：
        - 'WinRatio'            : 获利比例（%）
        - 'CostConcentration'   : 筹码集中度（%）
        - 'CircMarketCap'       : 流通市值（亿元）
        - 'TotalMarketCap'      : 总市值（亿元）
        - 'Condition1'          : WinRatio < N1
        - 'Condition2'          : CostConcentration < N2
        - 'Condition3'          : 最近30日中满足 CostConcentration < N2 的天数 >= 15
        - 'MarketCapCondition'  : 【已注释】TotalMarketCap >= MIN_MARKETCAP
        - 'LowPriceZone'        : CLOSE / HHV(HIGH,120) < 0.7
        - 'Selection'           : 选股条件综合结果（布尔）
        - 'VOL_MA5'             : 5 日均量
        - 'VOL_MA20'            : 20 日均量
        - 'VolumeActive'        : 量能是否放大（VOL_MA5 > VOL_MA20）
    """

    df = df.copy()

    # 基础价格与成交量序列（兼容大小写列名）
    close = _get_series(df, "close", "CLOSE")
    high = _get_series(df, "high", "HIGH")
    vol = _get_series(df, "vol", "VOL")

    # 财务数据：FINANCE(1) 和 FINANCE(40)
    finance_1 = _get_series(df, "FINANCE_1", "finance_1", "FINANCE1", "finance1")
    finance_40 = _get_series(df, "FINANCE_40", "finance_40", "FINANCE40", "finance40")

    # 公式参数
    N1 = n1
    N2 = n2
    MIN_MARKETCAP = min_marketcap

    # WinRatio:=WINNER(CLOSE)*100;
    df["WinRatio"] = _WINNER(close) * 100

    # CostConcentration:=(COST(95)-COST(5))/(COST(95)+COST(5))*100;
    cost_95 = _COST(close, vol, 95)
    cost_5 = _COST(close, vol, 5)
    denominator = cost_95 + cost_5
    df["CostConcentration"] = np.where(
        denominator != 0,
        (cost_95 - cost_5) / denominator * 100,
        np.nan,
    )

    # CircMarketCap:=FINANCE(40)/10000*CLOSE;
    # 注意：finance_40 单位是"万股"，需要除以10000转换为"亿股"，再乘以收盘价得到"亿元"
    df["CircMarketCap"] = finance_40 / 10000.0 * close

    # TotalMarketCap:=FINANCE(1)/10000*CLOSE;
    # 注意：finance_1 单位是"万股"，需要除以10000转换为"亿股"，再乘以收盘价得到"亿元"
    df["TotalMarketCap"] = finance_1 / 10000.0 * close
    
    # 添加调试信息：检查市值计算结果
    if len(df) > 0:
        latest_idx = df.index[-1]
        logger.debug(
            f"市值计算检查 - 收盘价={close.iloc[-1]:.2f}, "
            f"总股本={finance_1:.2f}万股, 流通股本={finance_40:.2f}万股, "
            f"总市值={df.loc[latest_idx, 'TotalMarketCap']:.2f}亿, "
            f"流通市值={df.loc[latest_idx, 'CircMarketCap']:.2f}亿"
        )

    # Condition1:=WinRatio<N1;
    df["Condition1"] = df["WinRatio"] < N1

    # Condition2:=CostConcentration<N2;
    df["Condition2"] = df["CostConcentration"] < N2

    # Condition3:=COUNT(CostConcentration<N2,30)>=15;
    cond_cc = df["CostConcentration"] < N2
    df["Condition3"] = mt.COUNT(cond_cc, 30) >= 15

    # ========== 注释掉市值条件相关逻辑 ==========
    # MarketCapCondition:=TotalMarketCap>=MIN_MARKETCAP;
    # df["MarketCapCondition"] = df["TotalMarketCap"] >= MIN_MARKETCAP
    logger.info("⚠️  已注释掉 MarketCapCondition（总市值≥80亿）筛选条件 ⚠️")

    # LowPriceZone:=CLOSE/HHV(HIGH,120)<0.7;
    hhv_120 = mt.HHV(high, 120)
    df["HHV120"] = hhv_120  # 保存120日最高价，便于日志输出
    df["Price_HHV_Ratio"] = close / hhv_120  # 保存价格/120日最高价比值
    df["LowPriceZone"] = df["Price_HHV_Ratio"] < 0.7

    # ========== 修改选股条件：移除 MarketCapCondition ==========
    # Selection:Condition1 AND Condition2 AND Condition3 AND MarketCapCondition AND LowPriceZone;
    # 改为：Selection:Condition1 AND Condition2 AND Condition3 AND LowPriceZone;
    df["Selection"] = (
        df["Condition1"]
        & df["Condition2"]
        & df["Condition3"]
        # & df["MarketCapCondition"]  # 注释掉市值条件
        & df["LowPriceZone"]
    )

    # VOL_MA5:=MA(VOL,5);
    df["VOL_MA5"] = mt.MA(vol, 5)

    # VOL_MA20:=MA(VOL,20);
    df["VOL_MA20"] = mt.MA(vol, 20)

    # VolumeActive:=VOL_MA5>VOL_MA20;
    df["VolumeActive"] = df["VOL_MA5"] > df["VOL_MA20"]

    return df


def get_price_df(stock_code: str, tdx_data_path: str) -> pd.DataFrame:
    """
    从本地通达信日线数据获取K线，并规范列名。
    返回列：date / open / high / low / close / vol
    """
    logger.info(f"获取股票 {stock_code} 的日线数据")
    reader = Reader.factory(market="std", tdxdir=tdx_data_path)
    df = reader.daily(symbol=stock_code)

    if df is None or df.empty:
        raise ValueError(f"未获取到 {stock_code} 的日线数据")

    # 日期列处理
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)

    # 规范列名
    rename_map = {}
    if "open" in df.columns:
        rename_map["open"] = "open"
    if "high" in df.columns:
        rename_map["high"] = "high"
    if "low" in df.columns:
        rename_map["low"] = "low"
    if "close" in df.columns:
        rename_map["close"] = "close"
    if "vol" in df.columns:
        rename_map["vol"] = "vol"
    elif "volume" in df.columns:
        rename_map["volume"] = "vol"

    df = df.rename(columns=rename_map)
    required = ["date", "open", "high", "low", "close", "vol"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{stock_code} 缺少必要列: {missing}")
    
    logger.info(f"股票 {stock_code} 日线数据获取成功，共 {len(df)} 条记录")
    return df[required]


def _with_market_prefix(stock_code: str) -> str:
    """根据代码补全 sh/sz 前缀。"""
    if stock_code.startswith(("60", "68", "90")):
        return f"sh{stock_code}"
    if stock_code.startswith(("00", "30", "38")):
        return f"sz{stock_code}"
    return stock_code


def get_finance_values(stock_code: str, tdx_data_path: str):
    """
    用 mootdx.finance 获取 FINANCE(1)/FINANCE(40) 对应的总股本/流通股本。
    通达信里常见字段：zgb(总股本)、ltgb(流通股本)。
    返回: (finance_1, finance_40) 单位：万股
    """
    logger.info(f"获取股票 {stock_code} 的财务数据")
    full_code = _with_market_prefix(stock_code)
    quotes = Quotes.factory(market="std", tdxdir=tdx_data_path)
    fin = quotes.finance(symbol=full_code)

    if fin is None or len(fin) == 0:
        raise ValueError(f"未获取到 {stock_code} 的财务数据")

    row = fin.iloc[0]
    
    # 打印所有列名和第一行数据，便于调试
    logger.info(f"股票 {stock_code} 财务数据列名: {list(fin.columns)}")
    logger.info(f"股票 {stock_code} 财务数据第一行: {row.to_dict()}")
    total_shares = None
    float_shares = None

    # 尝试多种可能的列名（总股本）
    total_candidates = [
        "zongguben", "总股本", "ZGB", "zgb", "ZongGuBen",
        "总股本(万股)", "总股本(股)", "总股本万股",
        "total_shares", "TotalShares", "TOTAL_SHARES"
    ]
    
    for cand in total_candidates:
        if cand in fin.columns:
            val = row[cand]
            if pd.notna(val):
                # 如果单位是"股"，需要除以10000转换为"万股"
                if isinstance(val, (int, float)) and val > 1000000:
                    # 可能是以"股"为单位，转换为"万股"
                    total_shares = float(val) / 10000.0
                    logger.debug(f"股票 {stock_code} 总股本从'股'转换为'万股': {val} -> {total_shares}")
                else:
                    total_shares = float(val)
                logger.info(f"股票 {stock_code} 找到总股本列 '{cand}' = {total_shares} 万股")
                if total_shares == 0:
                    logger.warning(f"⚠️  股票 {stock_code} 总股本为0，可能是数据问题！")
                break

    # 尝试多种可能的列名（流通股本）
    float_candidates = [
        "liutongguben", "流通股本", "LTGB", "ltgb", "LiuTongGuBen",
        "流通股本(万股)", "流通股本(股)", "流通股本万股",
        "已上市流通A股", "自由流通股(股)", "流通A股",
        "float_shares", "FloatShares", "FLOAT_SHARES",
        "outstanding", "Outstanding", "OUTSTANDING"
    ]
    
    for cand in float_candidates:
        if cand in fin.columns:
            val = row[cand]
            if pd.notna(val):
                # 如果单位是"股"，需要除以10000转换为"万股"
                if isinstance(val, (int, float)) and val > 1000000:
                    # 可能是以"股"为单位，转换为"万股"
                    float_shares = float(val) / 10000.0
                    logger.debug(f"股票 {stock_code} 流通股本从'股'转换为'万股': {val} -> {float_shares}")
                else:
                    float_shares = float(val)
                logger.info(f"股票 {stock_code} 找到流通股本列 '{cand}' = {float_shares} 万股")
                if float_shares == 0:
                    logger.warning(f"⚠️  股票 {stock_code} 流通股本为0，可能是数据问题！")
                break

    if total_shares is None or float_shares is None:
        error_msg = (
            f"{stock_code} 财务数据缺少总股本/流通股本字段\n"
            f"  当前列: {list(fin.columns)}\n"
            f"  总股本候选: {total_candidates}\n"
            f"  流通股本候选: {float_candidates}\n"
            f"  找到的总股本: {total_shares}\n"
            f"  找到的流通股本: {float_shares}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 检查值是否合理（总股本和流通股本应该大于0）
    if total_shares <= 0 or float_shares <= 0:
        logger.warning(
            f"股票 {stock_code} 财务数据异常：总股本={total_shares}万股，流通股本={float_shares}万股"
        )
    
    logger.info(f"股票 {stock_code} 财务数据：总股本={total_shares}万股，流通股本={float_shares}万股")
    # 直接按 FINANCE(1)/FINANCE(40) 使用，单位：万股
    return total_shares, float_shares


def calculate_stock_selection_for_code(
    stock_code: str,
    tdx_data_path: str,
    n1: int = 90,
    n2: int = 10,
    min_marketcap: float = 80,
) -> pd.DataFrame:
    """
    单只股票：拉取K线+财务，构造 FINANCE_1/FINANCE_40，调用公式。
    返回包含 Selection/VolumeActive 等信号的 DataFrame。
    """
    logger.info(f"开始计算股票 {stock_code} 的选股信号")
    price_df = get_price_df(stock_code, tdx_data_path)
    finance_1, finance_40 = get_finance_values(stock_code, tdx_data_path)

    # 检查财务数据是否有效
    if finance_1 <= 0 or finance_40 <= 0:
        logger.warning(
            f"股票 {stock_code} 财务数据异常：总股本={finance_1}万股，流通股本={finance_40}万股"
        )

    price_df["FINANCE_1"] = finance_1
    price_df["FINANCE_40"] = finance_40
    
    # 添加调试信息：检查计算前的值
    latest_close = price_df["close"].iloc[-1] if len(price_df) > 0 else 0
    logger.debug(
        f"股票 {stock_code} 计算市值前：收盘价={latest_close}, "
        f"总股本={finance_1}万股, 流通股本={finance_40}万股"
    )

    result_df = calculate_selection_signals(
        price_df, n1=n1, n2=n2, min_marketcap=min_marketcap
    )
    
    # 添加调试信息：检查计算后的值
    if len(result_df) > 0:
        latest_row = result_df.iloc[-1]
        logger.debug(
            f"股票 {stock_code} 计算市值后：总市值={latest_row.get('TotalMarketCap', 'N/A')}亿, "
            f"流通市值={latest_row.get('CircMarketCap', 'N/A')}亿"
        )
    
    logger.info(f"股票 {stock_code} 选股信号计算完成")
    return result_df


def calculate_all_stocks_selection(
    tdx_data_path: str,
    target_date: str | None = None,
    max_stocks: int | None = None,
    n1: int = 90,
    n2: int = 10,
    min_marketcap: float = 80,
    verbose: bool = True,
):
    """
    批量跑所有股票的 Selection 信号，并返回满足 Selection 的结果。
    - target_date: 指定日期（YYYY-MM-DD），如果没有该日期，则用最新一行。
    - max_stocks: 限制数量用于测试。
    - verbose: 是否打印过程信息，便于排查无结果问题。
    """
    if get_all_stock_codes is None or get_stock_name_map is None:
        raise ImportError("未能导入 get_all_stock_codes / get_stock_name_map，请检查路径。")

    stock_codes = get_all_stock_codes(tdx_data_path)
    if max_stocks:
        stock_codes = stock_codes[:max_stocks]
    logger.info(f"获取到 {len(stock_codes)} 只股票代码，限制最多处理 {max_stocks if max_stocks else '全部'} 只")

    # 批量获取名称映射，过滤 ST/*ST
    name_map = get_stock_name_map(stock_codes, tdx_data_path)
    filtered_codes = []
    for code in stock_codes:
        nm = name_map.get(code, code)
        if "ST" in nm or "*ST" in nm or "st" in nm or "*st" in nm:
            if verbose:
                logger.info(f"过滤ST股票: {code} {nm}")
            continue
        filtered_codes.append(code)
    stock_codes = filtered_codes
    logger.info(f"过滤ST后剩余 {len(stock_codes)} 只股票")

    results = []
    success_count = 0
    selection_count = 0
    errors = 0
    error_samples = []

    # 统计各条件满足数量（移除 MarketCapCondition 统计）
    condition_stats = {
        "Condition1": 0,
        "Condition2": 0,
        "Condition3": 0,
        # "MarketCapCondition": 0,  # 注释掉市值条件统计
        "LowPriceZone": 0,
        "Selection": 0
    }

    for idx, code in enumerate(stock_codes, 1):
        stock_name = name_map.get(code, code)
        logger.info(f"\n===== 处理第 {idx}/{len(stock_codes)} 只股票：{code} - {stock_name} =====")
        try:
            df = calculate_stock_selection_for_code(
                code,
                tdx_data_path,
                n1=n1,
                n2=n2,
                min_marketcap=min_marketcap,
            )
            if df is None or df.empty:
                logger.warning(f"股票 {code} 计算结果为空")
                errors += 1
                continue

            # 选取目标日期或最新
            if target_date:
                row_df = df[df["date"] == target_date]
                if row_df.empty:
                    logger.info(f"股票 {code} 无 {target_date} 数据，使用最新数据")
                    row_df = df.tail(1)
            else:
                row_df = df.tail(1)

            if row_df.empty:
                logger.warning(f"股票 {code} 无有效数据行")
                errors += 1
                continue

            row = row_df.iloc[0]
            success_count += 1

            # 提取关键指标值
            current_date = row["date"]
            close_price = round(row["close"], 2)
            win_ratio = round(row["WinRatio"], 2) if pd.notna(row["WinRatio"]) else np.nan
            cost_concentration = round(row["CostConcentration"], 2) if pd.notna(row["CostConcentration"]) else np.nan
            total_marketcap = round(row["TotalMarketCap"], 2) if pd.notna(row["TotalMarketCap"]) else np.nan
            circ_marketcap = round(row["CircMarketCap"], 2) if pd.notna(row["CircMarketCap"]) else np.nan
            price_hhv_ratio = round(row["Price_HHV_Ratio"], 3) if pd.notna(row["Price_HHV_Ratio"]) else np.nan
            
            # 提取各条件结果（移除 MarketCapCondition）
            cond1 = bool(row.get("Condition1", False))
            cond2 = bool(row.get("Condition2", False))
            cond3 = bool(row.get("Condition3", False))
            # cap_cond = bool(row.get("MarketCapCondition", False))  # 注释掉市值条件
            low_price = bool(row.get("LowPriceZone", False))
            selection = bool(row.get("Selection", False))
            vol_active = bool(row.get("VolumeActive", False))

            # 更新条件统计（移除 MarketCapCondition 统计）
            if cond1: condition_stats["Condition1"] += 1
            if cond2: condition_stats["Condition2"] += 1
            if cond3: condition_stats["Condition3"] += 1
            # if cap_cond: condition_stats["MarketCapCondition"] += 1
            if low_price: condition_stats["LowPriceZone"] += 1
            if selection: condition_stats["Selection"] += 1

            # 打印详细的中间过程（移除 MarketCapCondition 相关输出）
            logger.info(f"股票 {code} ({stock_name}) - 日期: {current_date}")
            logger.info(f"  关键指标：")
            logger.info(f"    收盘价: {close_price} | 获利比例: {win_ratio}% | 筹码集中度: {cost_concentration}%")
            logger.info(f"    总市值: {total_marketcap} 亿 | 流通市值: {circ_marketcap} 亿 | 价格/120日最高价: {price_hhv_ratio}")
            logger.info(f"  条件判定：")
            logger.info(f"    Condition1(获利比例<{n1}): {cond1} (当前值: {win_ratio})")
            logger.info(f"    Condition2(筹码集中度<{n2}): {cond2} (当前值: {cost_concentration})")
            logger.info(f"    Condition3(30天≥15天集中度<{n2}): {cond3}")
            # 注释掉市值条件输出
            # logger.info(f"    MarketCapCondition(总市值≥{min_marketcap}亿): {cap_cond} (当前值: {total_marketcap})")
            logger.info(f"    LowPriceZone(价格<120日高点7折): {low_price} (当前比值: {price_hhv_ratio})")
            logger.info(f"    VolumeActive(5日均量>20日均量): {vol_active}")
            logger.info(f"    最终选股结果(Selection): {selection}")

            if not selection:
                logger.info(f"股票 {code} 不满足最终选股条件")
                continue
            
            selection_count += 1
            logger.info(f"★★★ 股票 {code} ({stock_name}) 满足所有选股条件！★★★")

            results.append(
                {
                    "股票代码": code,
                    "股票名称": stock_name,
                    "日期": current_date,
                    "收盘价": close_price,
                    "WinRatio": win_ratio,
                    "CostConcentration": cost_concentration,
                    "流通市值(亿)": circ_marketcap,
                    "总市值(亿)": total_marketcap,
                    "VolumeActive": vol_active,
                    "Price_HHV_Ratio": price_hhv_ratio
                }
            )
        except Exception as ex:
            errors += 1
            error_msg = f"股票 {code} 处理出错: {str(ex)}"
            logger.error(error_msg)
            if len(error_samples) < 5:
                error_samples.append(error_msg)
            # 单个标的错误时跳过，避免中断全局
            continue

        if verbose and idx % 100 == 0:
            logger.info(f"[进度] 已处理 {idx}/{len(stock_codes)} 只 | 成功:{success_count} | 选中:{selection_count} | 错误:{errors}")

    # 打印统计总结（移除 MarketCapCondition 统计）
    logger.info(f"\n==================== 统计总结 ====================")
    logger.info(f"总股票数: {len(stock_codes)}")
    logger.info(f"成功处理: {success_count}")
    logger.info(f"选中股票: {selection_count}")
    logger.info(f"处理错误: {errors}")
    logger.info(f"\n各条件满足数量（在成功处理的股票中）：")
    for cond, count in condition_stats.items():
        rate = count / success_count * 100 if success_count > 0 else 0
        logger.info(f"  {cond}: {count} 只 ({rate:.1f}%)")
    
    if error_samples:
        logger.info(f"\n错误样例（前5个）：")
        for msg in error_samples:
            logger.info(f"  {msg}")

    if results:
        result_df = pd.DataFrame(results).sort_values("总市值(亿)", ascending=False).reset_index(drop=True)
        logger.info(f"\n最终选中 {len(result_df)} 只股票，列表如下：")
        logger.info(result_df.to_string(index=False))
        return result_df
    else:
        logger.info("\n⚠️  没有任何标的满足所有选股条件！")
        return pd.DataFrame()


__all__ = [
    "calculate_selection_signals",
    "get_price_df",
    "get_finance_values",
    "calculate_stock_selection_for_code",
    "calculate_all_stocks_selection",
]


if __name__ == "__main__":
    # 简单命令行示例：运行批量选股并打印结果条数
    tdx_path = "E:/new_tdx"  # 按需修改
    target_date = "2026-01-07"       # 例如 "2026-01-05"
    max_stocks = 100          # 测试时可限制数量

    logger.info("========== 开始批量选股任务（已注释市值条件）==========")
    try:
        df = calculate_all_stocks_selection(
            tdx_data_path=tdx_path,
            target_date=target_date,
            max_stocks=max_stocks,
            verbose=True,
        )
        logger.info(f"\n任务完成，最终选中 {len(df)} 只股票")
        if not df.empty:
            print("\n选中股票详情：")
            print(df)
        else:
            print("没有任何标的满足 Selection 条件。")
    except Exception as e:
        logger.error(f"运行出错: {str(e)}", exc_info=True)
        print("运行出错:", e)