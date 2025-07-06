import pandas as pd
import os
from mootdx.reader import Reader
from datetime import datetime

# 配置本地通达信路径
TDX_PATH = '/mnt/c/new_tdx'

def ensure_date_column(df):
    if 'date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df['date'] = df.index
        else:
            df = df.copy()
            df['date'] = pd.Series(
                pd.date_range(end=pd.Timestamp.today(), periods=len(df))
            ).values
    # 防止date既是index又是列
    if 'date' in df.index.names or isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index(drop=True)
    return df

# 获取最近N个交易日区间
def get_recent_trade_range(date, N):
    # 这里假设date为datetime.date对象
    # 用mootdx获取所有交易日
    reader = Reader.factory(market='std', tdxdir=TDX_PATH)
    # 任选一只股票，取其所有交易日
    df = None
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(TDX_PATH, f'vipdoc/{market}/lday')
        if not os.path.exists(lday_dir):
            continue
        for fname in os.listdir(lday_dir):
            if fname.endswith('.day'):
                symbol = fname[:8]
                df = reader.daily(symbol=symbol)
                if df is not None:
                    df = ensure_date_column(df)
                if df is not None and not df.empty:
                    break
        if df is not None and not df.empty:
            break
    if df is None or df.empty:
        raise RuntimeError('无法获取本地交易日')
    df = df.copy()
    df['date'] = pd.to_datetime(df['date']).dt.date
    all_dates = sorted(df['date'].unique())
    date = pd.to_datetime(date).date() if not isinstance(date, datetime) else date.date()
    if date not in all_dates:
        raise ValueError(f"指定日期{date}不在本地数据中")
    idx = all_dates.index(date)
    if idx < N:
        raise ValueError(f"本地数据不足N={N}天")
    start_date_str = all_dates[idx-N].strftime('%Y-%m-%d')
    end_date_str = all_dates[idx].strftime('%Y-%m-%d')
    return start_date_str, end_date_str

# 计算N日RPS，该函数需要传入date和N，返回date前N个交易日的RPS数据，并保存到rps_N表中。
def RPS(date,N=10):
    """
    计算每个股票今天收盘价相对于N个交易日前收盘价的涨幅（RPS），并保存到rps_N表，包含归一化排序字段。
    区间为（end_date_str, start_date_str]。
    """
    start_date_str, end_date_str = get_recent_trade_range(date, N)
    print(f"计算{N}日RPS，区间为（{start_date_str}, {end_date_str}]")
    reader = Reader.factory(market='std', tdxdir=TDX_PATH)
    results = []
    stock_count = 0
    # 遍历本地所有A股LDay文件
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(TDX_PATH, f'vipdoc/{market}/lday')
        if not os.path.exists(lday_dir):
            continue
        for fname in os.listdir(lday_dir):
            if not fname.endswith('.day'):
                continue
            code = fname[2:8]
            # 只保留A股常见板块
            if not (code.startswith(('600', '601', '603', '605', '688', '000', '001', '002', '003', '300', '301'))):
                continue
            symbol = fname[:8]
            stock_count += 1
            try:
                df = reader.daily(symbol=symbol)
                if df is not None:
                    df = ensure_date_column(df)
                if df is None or df.empty:
                    print(f"{symbol}: 本地数据为空")
                    continue
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df[(df['date'] > pd.to_datetime(start_date_str)) & (df['date'] <= pd.to_datetime(end_date_str))]
                df = df.sort_values('date').reset_index(drop=True)
                print(f"{symbol}: 区间数据行数={len(df)}, 区间=({start_date_str}, {end_date_str}], 全部日期范围={df['date'].min()}~{df['date'].max() if not df.empty else '无'}")
                if len(df) < 2:
                    continue
                close_N_days_ago = df.iloc[0]['close']
                close_today = df.iloc[-1]['close']
                if close_N_days_ago > 0:
                    rps = close_today / close_N_days_ago - 1
                else:
                    rps = None
                # 股票名称本地LDay无，留空
                stock_name = ''
                results.append((code, stock_name, rps, df.iloc[-1]['date'].strftime('%Y-%m-%d'), df.iloc[0]['date'].strftime('%Y-%m-%d')))
            except Exception as e:
                print(f"{symbol} 处理异常: {e}")
                continue
    # 保存到df中
    df_n = pd.DataFrame(results, columns=["code", "name", f"rps_{N}", f"today_date", f"N_days_ago_date"])
    df_n["code"] = df_n["code"].astype(str).str.zfill(6)
    # 归一化排序
    if not df_n.empty:
        rps_col = f"rps_{N}"
        df_n = df_n.sort_values(by=rps_col, ascending=False).reset_index(drop=True)
        df_n[f"rps_{N}_rank_num"] = df_n.index + 1
        total = len(df_n)
        if total > 1:
            df_n[f"rps_{N}_rank"] = ((total - df_n[f"rps_{N}_rank_num"]) / (total - 1) * 100).round(2)
        else:
            df_n[f"rps_{N}_rank"] = 100.0
    # 保存为csv
    df_n.to_csv(f"rps_{N}.csv", index=False, encoding='utf-8', float_format='%.6f')
    # 再次确保前导0不丢失
    # 用pandas的to_csv参数：将code列格式化为字符串
    # 但保险起见，建议用户读取csv时加dtype={'code':str}
    print(f"已保存到本地文件 rps_{N}.csv（如用Excel打开请注意code列格式）")
    print(f"遍历股票数: {stock_count}")
    print(f"最终有效RPS股票数: {len(results)}")


if __name__ == "__main__":
    date = datetime(2025, 7, 4).date()
    RPS(date,5)
    # RPS(date,10)
    # RPS(date,20)


