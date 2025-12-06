"""
板块交易拥挤度分析
计算近一年板块的交易拥挤度（交易拥挤度 = 板块成交额 / 市场总成交额）
"""
import akshare as ak
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timedelta
import warnings
import time
import os

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

warnings.filterwarnings('ignore')

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def calculate_market_total_amount(sector_data_list):
    """
    通过汇总所有板块成交额计算市场总成交额
    
    Args:
        sector_data_list: 板块数据列表，每个元素包含 (板块名称, DataFrame)
    
    Returns:
        DataFrame: 包含日期和总成交额的DataFrame
    """
    try:
        print("正在计算市场总成交额...")
        
        # 合并所有板块数据，添加板块名称
        all_sector_data = []
        for sector_name, sector_df in sector_data_list:
            if sector_df is None or sector_df.empty:
                continue
            sector_df_copy = sector_df.copy()
            sector_df_copy['sector'] = sector_name
            all_sector_data.append(sector_df_copy)
        
        if not all_sector_data:
            print("没有有效的板块数据")
            return None
        
        # 合并所有板块数据
        combined_df = pd.concat(all_sector_data, ignore_index=True)
        
        # 按日期汇总所有板块的成交额，得到市场总成交额
        market_total = combined_df.groupby('date')['amount'].sum().reset_index()
        market_total = market_total.rename(columns={'amount': 'total_amount'})
        market_total = market_total.sort_values('date')
        
        print(f"成功计算市场总成交额，共 {len(market_total)} 个交易日")
        return market_total
        
    except Exception as e:
        print(f"计算市场总成交额失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_sector_data(sector_name, start_date, end_date):
    """
    获取指定板块的历史数据
    
    Args:
        sector_name: 板块名称
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        DataFrame: 板块历史数据
    """
    try:
        # 获取板块历史数据
        df = ak.stock_board_industry_hist_em(
            symbol=sector_name,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        
        if df is None or df.empty:
            return None
        
        # 标准化列名
        column_mapping = {}
        if '日期' in df.columns:
            column_mapping['日期'] = 'date'
        elif 'date' not in df.columns:
            return None
        
        # 查找成交额列
        amount_col = None
        for col in ['成交额', 'amount', '成交金额']:
            if col in df.columns:
                amount_col = col
                break
        
        if amount_col is None:
            return None
        
        column_mapping[amount_col] = 'amount'
        df = df.rename(columns=column_mapping)
        
        # 确保有date和amount列
        if 'date' not in df.columns or 'amount' not in df.columns:
            return None
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # 清理数据：去除无效值
        df = df[df['amount'].notna()]
        df = df[df['amount'] > 0]
        
        return df[['date', 'amount']]
        
    except Exception as e:
        print(f"获取板块 {sector_name} 数据失败: {e}")
        return None


def calculate_congestion_ratio(sector_data_list, market_data):
    """
    计算交易拥挤度
    
    Args:
        sector_data_list: 板块数据列表，每个元素包含 (板块名称, DataFrame)
        market_data: 市场总成交额DataFrame
    
    Returns:
        DataFrame: 包含交易拥挤度的数据
    """
    # 合并所有板块数据
    all_sector_data = []
    
    for sector_name, sector_df in sector_data_list:
        if sector_df is None or sector_df.empty:
            continue
        
        sector_df = sector_df.copy()
        sector_df['sector'] = sector_name
        all_sector_data.append(sector_df)
    
    if not all_sector_data:
        print("没有有效的板块数据")
        return None
    
    # 合并所有板块数据
    combined_df = pd.concat(all_sector_data, ignore_index=True)
    
    # 按日期汇总每个板块的成交额
    daily_sector_amount = combined_df.groupby(['date', 'sector'])['amount'].sum().reset_index()
    
    # 计算每个板块每日的交易拥挤度
    result_list = []
    
    for date in daily_sector_amount['date'].unique():
        date_str = pd.to_datetime(date)
        market_row = market_data[market_data['date'] == date_str]
        
        if market_row.empty:
            continue
        
        market_amount = market_row['total_amount'].iloc[0]
        
        if pd.isna(market_amount) or market_amount <= 0:
            continue
        
        # 获取该日期所有板块的成交额
        date_sectors = daily_sector_amount[daily_sector_amount['date'] == date_str]
        
        for _, row in date_sectors.iterrows():
            sector_amount = row['amount']
            if pd.isna(sector_amount) or sector_amount <= 0:
                continue
            
            congestion_ratio = sector_amount / market_amount
            
            result_list.append({
                'date': date_str,
                'sector': row['sector'],
                'sector_amount': sector_amount,
                'market_amount': market_amount,
                'congestion_ratio': congestion_ratio
            })
    
    result_df = pd.DataFrame(result_list)
    
    if result_df.empty:
        print("计算交易拥挤度失败：没有有效数据")
        return None
    
    # 计算近一年平均交易拥挤度
    avg_congestion = result_df.groupby('sector').agg({
        'congestion_ratio': 'mean',
        'sector_amount': 'mean',
        'market_amount': 'mean'
    }).reset_index()
    
    avg_congestion = avg_congestion.rename(columns={
        'congestion_ratio': 'avg_congestion_ratio',
        'sector_amount': 'avg_sector_amount',
        'market_amount': 'avg_market_amount'
    })
    
    # 按交易拥挤度排序
    avg_congestion = avg_congestion.sort_values('avg_congestion_ratio', ascending=False)
    
    return avg_congestion, result_df


def plot_congestion_ratio(avg_congestion_df, daily_congestion_df=None):
    """
    绘制交易拥挤度图表
    
    Args:
        avg_congestion_df: 平均交易拥挤度DataFrame
        daily_congestion_df: 每日交易拥挤度DataFrame（可选，用于时序图）
    """
    # 创建图表
    fig = plt.figure(figsize=(16, 10))
    
    # 子图1：板块交易拥挤度排名（柱状图）
    ax1 = plt.subplot(2, 1, 1)
    
    # 只显示前20名
    top_n = min(20, len(avg_congestion_df))
    top_df = avg_congestion_df.head(top_n).copy()
    
    # 将拥挤度转换为百分比
    top_df['avg_congestion_ratio_pct'] = top_df['avg_congestion_ratio'] * 100
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(top_df)))
    bars = ax1.barh(range(len(top_df)), top_df['avg_congestion_ratio_pct'], color=colors)
    
    ax1.set_yticks(range(len(top_df)))
    ax1.set_yticklabels(top_df['sector'], fontsize=9)
    ax1.set_xlabel('平均交易拥挤度 (%)', fontsize=12)
    ax1.set_title(f'近一年板块交易拥挤度排名（前{top_n}名）', fontsize=14, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3, linestyle='--')
    ax1.invert_yaxis()  # 最高的在顶部
    
    # 在柱状图上添加数值标签
    for i, (idx, row) in enumerate(top_df.iterrows()):
        ax1.text(row['avg_congestion_ratio_pct'] + 0.01, i, 
                f"{row['avg_congestion_ratio_pct']:.2f}%",
                va='center', fontsize=8)
    
    # 子图2：交易拥挤度时序图（显示前10名板块）
    if daily_congestion_df is not None:
        ax2 = plt.subplot(2, 1, 2)
        
        top_10_sectors = avg_congestion_df.head(10)['sector'].tolist()
        daily_top = daily_congestion_df[daily_congestion_df['sector'].isin(top_10_sectors)].copy()
        
        # 转换为百分比
        daily_top['congestion_ratio_pct'] = daily_top['congestion_ratio'] * 100
        
        # 绘制每条线
        for sector in top_10_sectors:
            sector_data = daily_top[daily_top['sector'] == sector]
            if not sector_data.empty:
                ax2.plot(sector_data['date'], sector_data['congestion_ratio_pct'],
                        label=sector, alpha=0.7, linewidth=1.5)
        
        ax2.set_xlabel('日期', fontsize=12)
        ax2.set_ylabel('交易拥挤度 (%)', fontsize=12)
        ax2.set_title('近一年板块交易拥挤度时序图（前10名）', fontsize=14, fontweight='bold')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        ax2.grid(alpha=0.3, linestyle='--')
        
        # 格式化x轴日期
        ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    # 保存图片
    output_file = os.path.join(SCRIPT_DIR, f'板块交易拥挤度_{datetime.now().strftime("%Y%m%d")}.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n图表已保存到: {output_file}")
    
    plt.show()


def main():
    """主函数"""
    print("=" * 60)
    print("板块交易拥挤度分析程序")
    print("=" * 60)
    
    # 计算日期范围（近一年）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")
    
    print(f"\n分析时间范围: {start_date_str} 至 {end_date_str}")
    
    # 1. 获取一级板块列表
    print("\n正在获取一级板块列表...")
    try:
        sector_df = ak.stock_board_industry_name_em()
        if sector_df is None or sector_df.empty:
            print("获取板块列表失败")
            return
        
        sector_names = sector_df['板块名称'].tolist()
        print(f"共找到 {len(sector_names)} 个板块")
        
    except Exception as e:
        print(f"获取板块列表失败: {e}")
        return
    
    # 2. 获取每个板块的历史数据
    print(f"\n正在获取各板块历史数据（共{len(sector_names)}个板块）...")
    sector_data_list = []
    
    for i, sector_name in enumerate(sector_names, 1):
        print(f"[{i}/{len(sector_names)}] 正在获取板块: {sector_name}", end=" ... ")
        
        sector_data = get_sector_data(sector_name, start_date_str, end_date_str)
        
        if sector_data is not None and not sector_data.empty:
            sector_data_list.append((sector_name, sector_data))
            print("成功")
        else:
            print("失败")
        
        # 避免请求过快
        time.sleep(0.1)
        
        # 每10个板块打印一次进度
        if i % 10 == 0:
            print(f"  已完成 {i}/{len(sector_names)} 个板块，成功获取 {len(sector_data_list)} 个板块数据")
    
    print(f"\n成功获取 {len(sector_data_list)} 个板块的数据")
    
    if not sector_data_list:
        print("没有获取到有效的板块数据，程序退出")
        return
    
    # 3. 计算市场总成交额（通过汇总所有板块成交额）
    market_data = calculate_market_total_amount(sector_data_list)
    
    if market_data is None:
        print("\n无法计算市场总成交额数据，程序退出")
        return
    
    # 4. 计算交易拥挤度
    print("\n正在计算交易拥挤度...")
    result = calculate_congestion_ratio(sector_data_list, market_data)
    
    if result is None:
        print("计算交易拥挤度失败")
        return
    
    avg_congestion_df, daily_congestion_df = result
    
    # 5. 显示结果
    print("\n" + "=" * 60)
    print("板块交易拥挤度排名（前20名）")
    print("=" * 60)
    
    top_20 = avg_congestion_df.head(20).copy()
    top_20['avg_congestion_ratio_pct'] = top_20['avg_congestion_ratio'] * 100
    
    for idx, (_, row) in enumerate(top_20.iterrows(), 1):
        print(f"{idx:2d}. {row['sector']:20s} : {row['avg_congestion_ratio_pct']:6.2f}%")
    
    # 6. 保存数据
    output_csv = os.path.join(SCRIPT_DIR, f'板块交易拥挤度_{datetime.now().strftime("%Y%m%d")}.csv')
    avg_congestion_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n数据已保存到: {output_csv}")
    
    # 保存每日数据
    daily_output_csv = os.path.join(SCRIPT_DIR, f'板块交易拥挤度_每日数据_{datetime.now().strftime("%Y%m%d")}.csv')
    daily_congestion_df.to_csv(daily_output_csv, index=False, encoding='utf-8-sig')
    print(f"每日数据已保存到: {daily_output_csv}")
    
    # 7. 绘制图表
    print("\n正在生成图表...")
    plot_congestion_ratio(avg_congestion_df, daily_congestion_df)
    
    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

