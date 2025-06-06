#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import core.stockfetch as stf
from core.singleton_type import singleton_type


# 读取股票交易日历数据
class stock_trade_date(metaclass=singleton_type):
    def __init__(self):
        try:
            self.data = stf.fetch_stocks_trade_date()
        except Exception as e:
            logging.error(f"singleton.stock_trade_date处理异常：{e}")

    def get_data(self):
        return self.data
