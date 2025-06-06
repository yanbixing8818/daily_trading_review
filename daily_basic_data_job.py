#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import core.stockfetch as stf
from core.utils import schedule_trade_day_job
from core.stockfetch import fetch_stocks_trade_date

def job():
    now = datetime.datetime.now()
    stf.save_nph_stock_spot_data(now)
    stf.save_nph_etf_spot_data(now)


if __name__ == '__main__':
    schedule_trade_day_job(job, 15, 30)

