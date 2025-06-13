import baostock as bs
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

def get_wind_a_turnover_baostock(start_date=None, end_date=None):
    """使用baostock获取万得全A指数换手率"""
    if start_date is None:
        # 默认获取近30天数据
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    
    if end_date is None:
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # 登录系统
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return None
    
    try:
        # 获取指数数据，万得全A指数代码: 000002.SH
        rs = bs.query_history_k_data_plus(
            "000002.SH",
            "date,code,close,pctChg,turn",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 复权类型，1：后复权，2：前复权，3：不复权
        )
        
        if rs.error_code != '0':
            print(f"查询失败: {rs.error_msg}")
            return None
        
        # 转换数据格式
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        # 登出系统
        bs.logout()
        
        # 转换为DataFrame
        result = pd.DataFrame(data_list, columns=rs.fields)
        
        # 转换数据类型
        result['close'] = pd.to_numeric(result['close'])
        result['pctChg'] = pd.to_numeric(result['pctChg'])
        result['turn'] = pd.to_numeric(result['turn'])
        
        return result
    except Exception as e:
        print(f"获取万得全A指数数据出错: {e}")
        bs.logout()
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
    line1 = ax1.plot(turnover_data['date'], turnover_data['turn'], 'b-', label='换手率(%)')
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
    ax1.set_xticks(range(0, n, step))
    ax1.set_xticklabels(turnover_data['date'][::step], rotation=45, ha='right')
    
    # 添加图例
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    plt.title('万得全A指数换手率和收盘价')
    plt.grid(True)
    
    # 调整布局，确保标签不被切掉
    plt.tight_layout()
    plt.savefig('wind_a_turnover_baostock.png', bbox_inches='tight', dpi=300)
    plt.show()

def main():
    # 获取用户输入的日期范围
    start_date = input("请输入开始日期 (YYYY-MM-DD, 例如: 2023-01-01), 直接回车使用默认值: ")
    if not start_date:
        start_date = None
    
    end_date = input("请输入结束日期 (YYYY-MM-DD, 例如: 2023-12-31), 直接回车使用默认值: ")
    if not end_date:
        end_date = None
    
    print("正在获取万得全A指数换手率数据...")
    turnover_data = get_wind_a_turnover_baostock(start_date, end_date)
    
    if turnover_data is not None and not turnover_data.empty:
        # 显示最近5天的换手率数据
        print("\n最近5天的万得全A指数换手率:")
        recent_data = turnover_data.tail(5)[['date', 'close', 'turn']]
        print(recent_data)
        
        # 计算统计指标
        avg_turnover = turnover_data['turn'].mean()
        max_turnover = turnover_data['turn'].max()
        min_turnover = turnover_data['turn'].min()
        
        print(f"\n统计指标:")
        print(f"平均换手率: {avg_turnover:.2f}%")
        print(f"最高换手率: {max_turnover:.2f}%")
        print(f"最低换手率: {min_turnover:.2f}%")
        
        # 绘制图表
        print("\n正在生成换手率图表...")
        plot_wind_a_turnover(turnover_data)
        
        # 保存数据
        turnover_data.to_csv('wind_a_turnover_baostock.csv', index=False, encoding='utf-8-sig')
        print(f"数据已保存到 wind_a_turnover_baostock.csv")
    else:
        print("获取数据失败或没有找到数据。")

if __name__ == "__main__":
    main()