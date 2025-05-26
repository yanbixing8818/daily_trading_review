# 每日复盘

1. 涨跌停数量随时间变化图表
python文件：analyze_limit_up_down.py
执行命令：python3 analyze_limit_up_down.py
结果：生成output.png 和 recent_30_days_limit_up_down.xlsx


2. A股市场数据分析
python文件：calc_all_a_stock_data.py
执行命令：streamlit run calc_all_a_stock_data.py
点击生成的网址，可以看到一些数据；
点击网页上的导出数据，生成：A股市场数据.xlsx


3. 统计板块区间涨幅生成热力图
python文件：Sector_Interval_Performance_Analysis.py
执行命令：streamlit run Sector_Interval_Performance_Analysis.py
点击生成的网址，可以看到热力图。


4. 涨停原因 
python文件：zhangtingyuanyin.py
执行命令：streamlit run py_script/zhangtingyuanyin.py
点击生成的网址，可以看到涨停原因分组后的表格，并且按照涨停原因生成热力图，方便看出板块效应。


5. 钉钉复盘v1
python文件：dingding_fupan1.py
执行命令：python3 dingding_fupan1.py
会直接把涨停原因里面的3张图发送到钉钉群里面。

6. 连板天梯
python文件：lianbantianti.py
执行命令：streamlit run lianbantianti.py
点击生成的网址，可以看到连板天梯图。


7. 异动提醒
python文件：yidongqingkuang.py
执行命令：python3 yidongqingkuang.py
生成：异动情况统计表_matplotlib.png

现在这个脚本还有问题：
1) 获取10日/30日的涨幅，不是简单的获取今天对比10日前的涨幅，而应该判断10日内的最大涨幅。有可能10日前到8日前这两天是跌的，最低价是7日前这一天。
2) 目前获取涨幅的函数还有问题，很多标的没有获取到，导致最终的计算结果不全。
3) 还需要添加已异动的股票去除机制。


8. 添加dongcai数据抓取方式
core/crawling 文件夹放数据的抓取方式
core/crawling/stock_hist_em.py   函数实现
core/crawling/stock_hist_em.txt  对应python文件做的一些实验和函数解释说明
core/crawling/stock_hist_em.py   整个抓取方式的函数总结

9. 添加钉钉复盘
python文件：dingtalk_daily_trading_review.py
执行命令：python3 dingtalk_daily_trading_review.py
结果：自动开始复盘，发送到dingding群内。






