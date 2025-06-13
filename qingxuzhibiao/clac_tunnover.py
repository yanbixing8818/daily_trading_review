import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime, timedelta
from tqdm import tqdm
import argparse

def get_stock_list():
    """获取A股股票列表"""
    try:
        # 获取沪深A股股票代码和名称
        stock_info = ak.stock_zh_a_spot_em()
        return stock_info[['代码', '名称']]
    except Exception as e:
        print(f"获取股票列表出错: {e}")
        return None

def get_stock_circulation_shares(stock_code):
    """获取股票的流通股数量"""
    try:
        # 获取股票的基本信息，包括流通股本
        stock_info = ak.stock_individual_info_em(symbol=stock_code)
        
        # 查找流通股本信息
        circulation_row = stock_info[stock_info['item'] == '流通股本']
        if not circulation_row.empty:
            # 流通股本单位为亿股，转换为股
            circulation_shares = float(circulation_row['value'].values[0]) * 100000000
            return circulation_shares
        else:
            print(f"未找到股票 {stock_code} 的流通股本信息")
            return None
    except Exception as e:
        print(f"获取股票 {stock_code} 流通股本信息出错: {e}")
        return None

def get_stock_daily_data(stock_code, start_date, end_date):
    """获取股票的日交易数据"""
    try:
        # 使用akshare获取A股历史数据
        # 注意：成交量单位为股
        stock_data = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="qfq")
        return stock_data
    except Exception as e:
        print(f"获取股票 {stock_code} 历史数据出错: {e}")
        return None

def calculate_turnover_rate(stock_data, circulation_shares):
    """计算换手率"""
    if stock_data is None or circulation_shares is None:
        return None
    
    # 确保数据按日期排序
    stock_data = stock_data.sort_values('日期')
    
    # 计算换手率: 成交量/流通股总股数
    stock_data['换手率'] = stock_data['成交量'] / circulation_shares * 100  # 转换为百分比
    
    return stock_data

def plot_turnover_rate(stock_data, stock_code, stock_name):
    """绘制换手率图表"""
    if stock_data is None or len(stock_data) == 0:
        return
    
    # 创建一个新的图形
    plt.figure(figsize=(14, 8))
    
    # 绘制收盘价
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(stock_data['日期'], stock_data['收盘'], 'b-', label='收盘价')
    ax1.set_title(f'{stock_code} {stock_name} 收盘价与换手率分析')
    ax1.set_ylabel('价格')
    ax1.legend()
    ax1.grid(True)
    
    # 绘制换手率
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    ax2.bar(stock_data['日期'], stock_data['换手率'], color='r', alpha=0.7, label='换手率(%)')
    ax2.set_xlabel('日期')
    ax2.set_ylabel('换手率(%)')
    ax2.legend()
    ax2.grid(True)
    
    # 自动调整日期标签
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.tight_layout()
    
    # 保存图表
    if not os.path.exists('turnover_charts'):
        os.makedirs('turnover_charts')
    plt.savefig(f'turnover_charts/{stock_code}_turnover.png')
    plt.show()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='计算A股换手率')
    parser.add_argument('--stock', type=str, help='股票代码，例如: 000001')
    parser.add_argument('--days', type=int, default=30, help='分析的天数，默认为30天')
    parser.add_argument('--all', action='store_true', help='是否分析所有股票')
    args = parser.parse_args()
    
    # 计算日期范围
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y%m%d')
    
    if args.all:
        # 获取所有股票列表
        print("获取所有A股股票列表...")
        stock_list = get_stock_list()
        if stock_list is None or len(stock_list) == 0:
            print("未获取到股票列表，程序退出。")
            return
        
        # 分析所有股票
        print(f"开始分析 {len(stock_list)} 只股票的换手率...")
        
        # 创建结果目录
        if not os.path.exists('turnover_results'):
            os.makedirs('turnover_results')
        
        all_stocks_results = []
        
        for _, row in tqdm(stock_list.iterrows(), total=len(stock_list)):
            stock_code = row['代码']
            stock_name = row['名称']
            
            # 获取流通股本
            circulation_shares = get_stock_circulation_shares(stock_code)
            if circulation_shares is None:
                continue
            
            # 获取历史数据
            stock_data = get_stock_daily_data(stock_code, start_date, end_date)
            if stock_data is None or len(stock_data) == 0:
                continue
            
            # 计算换手率
            turnover_data = calculate_turnover_rate(stock_data, circulation_shares)
            if turnover_data is None:
                continue
            
            # 保存单个股票的详细数据
            turnover_data.to_csv(f'turnover_results/{stock_code}_turnover.csv', index=False, encoding='utf-8-sig')
            
            # 计算统计指标
            avg_turnover = turnover_data['换手率'].mean()
            max_turnover = turnover_data['换手率'].max()
            min_turnover = turnover_data['换手率'].min()
            
            # 记录结果
            all_stocks_results.append({
                '股票代码': stock_code,
                '股票名称': stock_name,
                '平均换手率': f"{avg_turnover:.2f}%",
                '最高换手率': f"{max_turnover:.2f}%",
                '最低换手率': f"{min_turnover:.2f}%",
                '分析天数': len(turnover_data)
            })
            
            # 每分析100只股票输出一次进度
            if len(all_stocks_results) % 100 == 0:
                print(f"已分析 {len(all_stocks_results)} 只股票...")
        
        # 保存所有股票的统计结果
        if all_stocks_results:
            results_df = pd.DataFrame(all_stocks_results)
            results_df.to_csv('turnover_results/all_stocks_turnover_stats.csv', index=False, encoding='utf-8-sig')
            print(f"分析完成！共分析 {len(all_stocks_results)} 只股票。")
            print(f"统计结果已保存到 turnover_results/all_stocks_turnover_stats.csv")
        else:
            print("没有成功分析任何股票。")
            
    else:
        # 分析单只股票
        stock_code = args.stock
        if not stock_code:
            stock_code = input("请输入股票代码（例如：000001）: ")
        
        # 获取股票名称
        stock_list = get_stock_list()
        stock_info = stock_list[stock_list['代码'] == stock_code]
        if stock_info.empty:
            print(f"未找到股票代码 {stock_code}，请检查输入是否正确。")
            return
        
        stock_name = stock_info['名称'].values[0]
        
        print(f"开始分析 {stock_code} {stock_name} 的换手率...")
        
        # 获取流通股本
        circulation_shares = get_stock_circulation_shares(stock_code)
        if circulation_shares is None:
            print(f"无法获取 {stock_code} 的流通股本信息，程序退出。")
            return
        
        print(f"{stock_code} 流通股本: {circulation_shares/100000000:.2f} 亿股")
        
        # 获取历史数据
        stock_data = get_stock_daily_data(stock_code, start_date, end_date)
        if stock_data is None or len(stock_data) == 0:
            print(f"未获取到 {stock_code} 的历史交易数据，程序退出。")
            return
        
        # 计算换手率
        turnover_data = calculate_turnover_rate(stock_data, circulation_shares)
        
        if turnover_data is not None:
            # 显示结果
            print("\n===== 换手率分析结果 =====")
            print(f"分析日期范围: {start_date} 至 {end_date}")
            print(f"分析天数: {len(turnover_data)} 天")
            print(f"平均换手率: {turnover_data['换手率'].mean():.2f}%")
            print(f"最高换手率: {turnover_data['换手率'].max():.2f}%")
            print(f"最低换手率: {turnover_data['换手率'].min():.2f}%")
            
            # 显示最近5天的换手率
            print("\n最近5天的换手率:")
            recent_data = turnover_data.tail(5)[['日期', '收盘', '换手率']]
            recent_data['日期'] = pd.to_datetime(recent_data['日期'])
            recent_data['日期'] = recent_data['日期'].dt.strftime('%Y-%m-%d')
            print(recent_data)
            
            # 绘制图表
            print("\n正在生成换手率图表...")
            plot_turnover_rate(turnover_data, stock_code, stock_name)
            
            # 保存数据
            if not os.path.exists('turnover_results'):
                os.makedirs('turnover_results')
            turnover_data.to_csv(f'turnover_results/{stock_code}_turnover.csv', index=False, encoding='utf-8-sig')
            print(f"详细数据已保存到 turnover_results/{stock_code}_turnover.csv")
        else:
            print("换手率计算失败。")

if __name__ == "__main__":
    main()



# 分析单只股票：python a_share_turnover.py --stock 000001 --days 60
# 分析所有股票：python a_share_turnover.py --all --days 30