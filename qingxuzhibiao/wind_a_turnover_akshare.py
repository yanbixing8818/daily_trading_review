import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

def get_wind_a_turnover(start_date=None, end_date=None):
    """获取万得全A指数换手率"""
    if start_date is None:
        # 默认获取近30天数据
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')
    
    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y%m%d')
    
    try:
        # 转换日期格式为datetime对象
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # 检查日期范围
        if start_dt > end_dt:
            print("开始日期不能晚于结束日期")
            return None
            
        # 检查日期是否太早
        min_date = pd.to_datetime('20100101')  # akshare 万得全A指数数据最早从2010年开始
        if start_dt < min_date:
            print(f"开始日期不能早于 {min_date.strftime('%Y%m%d')}")
            return None
            
        # 检查日期是否在未来
        if end_dt > pd.to_datetime(datetime.datetime.now()):
            print("结束日期不能超过今天")
            return None
        
        # 使用akshare获取指数历史数据，包含换手率
        # 万得全A指数代码：881001
        index_data = ak.index_zh_a_hist(symbol="881001", period="daily", 
                                       start_date=start_date, end_date=end_date)
        
        # 检查数据是否为空
        if index_data is None or index_data.empty:
            print("获取数据为空")
            return None
            
        # 确保必要的列存在
        required_columns = ['日期', '收盘', '换手率']
        if not all(col in index_data.columns for col in required_columns):
            print(f"数据缺少必要的列，当前列名: {index_data.columns.tolist()}")
            return None
        
        # 重命名列以统一格式
        index_data = index_data.rename(columns={
            '日期': 'date',
            '换手率': 'turnover',
            '收盘': 'close'
        })
        
        # 转换日期格式
        index_data['date'] = pd.to_datetime(index_data['date'])
        
        # 确保数据按日期排序
        index_data = index_data.sort_values('date')
        
        return index_data
    except Exception as e:
        print(f"获取万得全A指数数据出错: {str(e)}")
        print("请检查网络连接或确认akshare版本是否最新")
        return None

def plot_wind_a_turnover(turnover_data):
    """绘制万得全A指数换手率和收盘价图表"""
    if turnover_data is None or turnover_data.empty:
        print("没有数据可绘制")
        return
    
    plt.figure(figsize=(14, 8))
    
    # 创建双y轴图表
    ax1 = plt.gca()
    ax2 = ax1.twinx()
    
    # 绘制换手率（左y轴）
    line1 = ax1.plot(turnover_data['date'], turnover_data['turnover'], 'b-', label='换手率(%)')
    ax1.set_xlabel('日期')
    ax1.set_ylabel('换手率(%)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    
    # 绘制指数收盘价（右y轴）
    line2 = ax2.plot(turnover_data['date'], turnover_data['close'], 'r-', label='指数收盘价')
    ax2.set_ylabel('指数值', color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    
    # 优化x轴日期显示
    # 计算合适的显示间隔
    n = len(turnover_data['date'])
    step = max(1, n // 10)  # 根据数据量自动调整显示间隔
    
    # 设置x轴刻度和标签
    ax1.set_xticks(turnover_data['date'][::step])
    ax1.set_xticklabels(turnover_data['date'].dt.strftime('%Y-%m-%d')[::step], rotation=45, ha='right')
    
    # 添加图例
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    plt.title('万得全A指数换手率和收盘价')
    plt.grid(True)
    
    # 调整布局，确保标签不被切掉
    plt.tight_layout()
    plt.savefig('wind_a_turnover.png', bbox_inches='tight', dpi=300)
    plt.show()

def main():
    # 获取用户输入的日期范围
    start_date = input("请输入开始日期 (YYYYMMDD, 例如: 20230101), 直接回车使用默认值: ")
    if not start_date:
        start_date = None
    
    end_date = input("请输入结束日期 (YYYYMMDD, 例如: 20231231), 直接回车使用默认值: ")
    if not end_date:
        end_date = None
    
    print("正在获取万得全A指数换手率数据...")
    turnover_data = get_wind_a_turnover(start_date, end_date)
    
    if turnover_data is not None and not turnover_data.empty:
        # 显示最近5天的换手率数据
        print("\n最近5天的万得全A指数换手率:")
        recent_data = turnover_data.tail(5)[['date', 'close', 'turnover']]
        print(recent_data)
        
        # 计算统计指标
        avg_turnover = turnover_data['turnover'].mean()
        max_turnover = turnover_data['turnover'].max()
        min_turnover = turnover_data['turnover'].min()
        
        print(f"\n统计指标:")
        print(f"平均换手率: {avg_turnover:.2f}%")
        print(f"最高换手率: {max_turnover:.2f}%")
        print(f"最低换手率: {min_turnover:.2f}%")
        
        # 绘制图表
        print("\n正在生成换手率图表...")
        plot_wind_a_turnover(turnover_data)
        
        # 保存数据
        turnover_data.to_csv('wind_a_turnover.csv', index=False, encoding='utf-8-sig')
        print(f"数据已保存到 wind_a_turnover.csv")
    else:
        print("获取数据失败或没有找到数据。")

if __name__ == "__main__":
    main()


    #akshare 万得全A指数数据最早好像只能用20211201开始。
