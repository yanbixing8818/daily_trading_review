#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os.path
import datetime
import numpy as np
import pandas as pd

import core.crawling.stock_hist_em as she
import core.crawling.fund_etf_em as fee
import core.tablestructure as tbs
import core.database as mdb

# 600 601 603 605开头的股票是上证A股
# 600开头的股票是上证A股，属于大盘股，其中6006开头的股票是最早上市的股票，
# 6016开头的股票为大盘蓝筹股；900开头的股票是上证B股；
# 688开头的是上证科创板股票；
# 000开头的股票是深证A股，001、002开头的股票也都属于深证A股，
# 其中002开头的股票是深证A股中小企业股票；
# 200开头的股票是深证B股；
# 300、301开头的股票是创业板股票；400开头的股票是三板市场股票。
# 430、83、87开头的股票是北证A股
def is_a_stock(code):
    # 上证A股  # 深证A股
    return code.startswith(('600', '601', '603', '605', '000', '001', '002', '003', '300', '301'))


# 过滤掉 st 股票。
def is_not_st(name):
    return not name.startswith(('*ST', 'ST'))


# 过滤价格，如果没有基本上是退市了。
def is_open(price):
    return not np.isnan(price)


def is_open_with_line(price):
    return price != '-'



# 读取当天股票数据
def fetch_stocks(date):
    try:
        data = she.stock_zh_a_spot_em()
        print(data)
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_SPOT['columns'])
        data = data.loc[data['code'].apply(is_a_stock)].loc[data['new_price'].apply(is_open)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks处理异常：{e}")
    return None


# 读取当天基金etf数据
def fetch_etfs(date):
    try:
        data = fee.fund_etf_spot_em()
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_ETF_SPOT['columns'])
        data = data.loc[data['new_price'].apply(is_open)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_etfs处理异常：{e}")
    return None


# 股票实时行情数据。
def save_nph_stock_spot_data(date):
    # 股票列表
    try:
        data = fetch_stocks(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_SPOT['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_SPOT['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")

    except Exception as e:
        logging.error(f"basic_data_daily_job.save_stock_spot_data处理异常：{e}")


# 基金实时行情数据。
def save_nph_etf_spot_data(date):
    # 基金etf列表
    try:
        data = fetch_etfs(date)
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_ETF_SPOT['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_ETF_SPOT['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_daily_job.save_nph_etf_spot_data处理异常：{e}")






if __name__ == "__main__":
    # save_nph_stock_spot_data(datetime.datetime.now())
    save_nph_etf_spot_data(datetime.datetime.now())
