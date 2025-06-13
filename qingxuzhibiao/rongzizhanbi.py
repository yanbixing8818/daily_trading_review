# 融资融券数据，都是从：https://www.szse.cn/disclosure/margin/margin/index.html
# 这里抓取的，如果akshare不稳定的话，尝试直接抓取网页







import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

def get_margin_trading_ratio(start_date=None, end_date=None):
    """获取融资买入额占总成交额的比重"""
    if start_date is None:
        # 默认获取近30天数据
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')
    
    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y%m%d')
    
    try:
        # 生成日期列表
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        margin_data_list = []
        
        # 获取每个日期的融资融券数据
        for date in date_range:
            date_str = date.strftime('%Y%m%d')
            try:
                # 获取融资融券数据
                daily_data = ak.stock_margin_szse(date=date_str)
                print(f"{date_str}: {daily_data}")
                if isinstance(daily_data, pd.DataFrame) and not daily_data.empty:
                    # 添加日期列
                    daily_data['日期'] = date
                    margin_data_list.append(daily_data)
            except Exception:
                continue
        
        if not margin_data_list:
            print("未获取到任何融资融券数据")
            return None
            
        # 合并所有数据
        margin_data = pd.concat(margin_data_list, ignore_index=True)
        
        # 获取每日成交额数据
        index_data = ak.index_zh_a_hist(symbol="881001", period="daily", 
                                       start_date=start_date, end_date=end_date)
        if index_data is None or index_data.empty:
            print("未获取到成交额数据")
            return None
            
        # 合并融资融券数据和成交额数据
        margin_data['日期'] = pd.to_datetime(margin_data['日期'])
        index_data['日期'] = pd.to_datetime(index_data['日期'])
        merged_data = pd.merge(margin_data, index_data[['日期', '成交额']], on='日期', how='inner')
        
        # 去除无效数据
        merged_data = merged_data.dropna(subset=['融资买入额', '成交额'])
        merged_data = merged_data[merged_data['成交额'] > 0]
        
        # 计算融资买入额占比
        merged_data['融资买入额占比'] = merged_data['融资买入额'] / merged_data['成交额'] * 100
        
        # 去除无效数据
        merged_data = merged_data.replace([float('inf'), -float('inf')], pd.NA).dropna(subset=['融资买入额占比'])
        
        # 重命名列
        result = merged_data[['日期', '融资买入额占比']].rename(columns={
            '日期': 'date',
            '融资买入额占比': 'margin_ratio'
        })
        
        return result
    except Exception as e:
        print(f"获取融资融券数据出错: {str(e)}")
        return None

def get_wind_a_index(start_date=None, end_date=None):
    """获取万得全A指数数据"""
    if start_date is None:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')
    
    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y%m%d')
    
    try:
        # 获取万得全A指数数据
        index_data = ak.index_zh_a_hist(symbol="881001", period="daily", 
                                       start_date=start_date, end_date=end_date)
        
        if index_data is None or index_data.empty:
            return None
            
        # 重命名列
        index_data = index_data.rename(columns={
            '日期': 'date',
            '收盘': 'close'
        })
        
        # 转换日期格式
        index_data['date'] = pd.to_datetime(index_data['date'])
        
        return index_data[['date', 'close']]
    except Exception as e:
        print(f"获取万得全A指数数据出错: {str(e)}")
        return None

def plot_margin_ratio_and_index(margin_data, index_data):
    """绘制融资买入额占比和指数走势图"""
    if margin_data is None or index_data is None or margin_data.empty or index_data.empty:
        print("数据为空，无法绘图")
        return
    
    # 只保留两者都存在的日期
    plot_data = pd.merge(margin_data, index_data, on='date', how='inner')
    if plot_data.empty:
        print("合并后无有效数据，无法绘图")
        return
    
    plt.figure(figsize=(14, 8))
    
    # 创建双y轴图表
    ax1 = plt.gca()
    ax2 = ax1.twinx()
    
    # 绘制融资买入额占比（左y轴）
    line1 = ax1.plot(plot_data['date'], plot_data['margin_ratio'], 'b-', label='融资买入额占比(%)')
    ax1.set_xlabel('日期')
    ax1.set_ylabel('融资买入额占比(%)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    
    # 绘制指数走势（右y轴）
    line2 = ax2.plot(plot_data['date'], plot_data['close'], 'r-', label='万得全A指数')
    ax2.set_ylabel('指数值', color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    
    # 优化x轴日期显示
    n = len(plot_data['date'])
    step = max(1, n // 10)
    
    # 设置x轴刻度和标签
    ax1.set_xticks(plot_data['date'][::step])
    ax1.set_xticklabels(plot_data['date'].dt.strftime('%Y-%m-%d')[::step], rotation=45, ha='right')
    
    # 添加图例
    lines = line1 + line2
    labels = ['融资买入额占比(%)', '万得全A指数']
    ax1.legend(lines, labels, loc='upper left')
    ax2.legend(loc='upper right')
    
    plt.title('融资买入额占比与万得全A指数走势')
    plt.grid(True)
    
    # 调整布局
    plt.tight_layout()
    plt.savefig('margin_ratio_and_index.png', bbox_inches='tight', dpi=300)
    plt.show()

def main():
    # 获取用户输入的日期范围
    start_date = input("请输入开始日期 (YYYYMMDD, 例如: 20230101), 直接回车使用默认值: ")
    if not start_date:
        start_date = None
    
    end_date = input("请输入结束日期 (YYYYMMDD, 例如: 20231231), 直接回车使用默认值: ")
    if not end_date:
        end_date = None
    
    print("正在获取数据...")
    
    # 获取融资买入额占比数据
    margin_data = get_margin_trading_ratio(start_date, end_date)
    if margin_data is None or margin_data.empty:
        print("获取融资融券数据失败")
        return
    
    # 获取指数数据
    index_data = get_wind_a_index(start_date, end_date)
    if index_data is None or index_data.empty:
        print("获取指数数据失败")
        return
    
    # 显示统计信息
    print("\n融资买入额占比统计:")
    print(f"平均占比: {margin_data['margin_ratio'].mean():.2f}%")
    print(f"最高占比: {margin_data['margin_ratio'].max():.2f}%")
    print(f"最低占比: {margin_data['margin_ratio'].min():.2f}%")
    
    # 绘制图表
    print("\n正在生成图表...")
    plot_margin_ratio_and_index(margin_data, index_data)
    
    # 保存数据
    margin_data.to_csv('margin_ratio.csv', index=False, encoding='utf-8-sig')
    index_data.to_csv('wind_a_index.csv', index=False, encoding='utf-8-sig')
    print("数据已保存到 margin_ratio.csv 和 wind_a_index.csv")

if __name__ == "__main__":
    main()
