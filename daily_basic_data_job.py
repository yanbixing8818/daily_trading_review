#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from core.stockfetch import save_nph_etf_spot_data
from core.stockfetch import save_nph_stock_spot_data
from core.utils import schedule_trade_day_jobs
from core.utils import get_recent_trade_range
from core.crawling.stock_hist_baostock import get_all_hist_k_data_and_save
from dingtalk_subjob.calc_abnormal import send_abnormal_to_dingtalk

def job():
    today = datetime.now().date()
    
    #从东财抓取股票和基金的实时行情数据
    save_nph_stock_spot_data(today)
    save_nph_etf_spot_data(today)
    
    #从baostock抓取股票今天的历史数据
    start_date_str, end_date_str = get_recent_trade_range(today, 1)
    print(start_date_str, end_date_str)
    get_all_hist_k_data_and_save(start_date_str, end_date_str)

    #计算异动情况
    send_abnormal_to_dingtalk()

    #更新股票的rps


if __name__ == '__main__':
    schedule_trade_day_jobs(job, [(18, 00)])
    # job()

